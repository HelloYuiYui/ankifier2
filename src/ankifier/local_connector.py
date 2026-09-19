"""Client for the local MLX LLM server (see llm_server/server.py).

Mirrors mistral_connector's interface so the two are interchangeable.

The instruction block and the word are sent as a *single user message* rather
than a system message plus a user message: Mistral's instruct chat templates
require strict user/assistant alternation and reject a standalone `system`
role.  The instruction block still comes first and is byte-identical on every
request, so mlx-lm can still reuse the cached KV prefix and only prefill the
few tokens of the word itself.
"""
import json
import os
import re
from dataclasses import dataclass

import requests

from ankifier.mistral_connector import _build_cloze, clean_sense
from ankifier.models import VALID_LEVELS, Level, Sense, WordEntry


@dataclass
class LocalLLMClient:
    """Connection details for the local MLX server."""
    base_url: str
    model: str
    timeout: int


def init_client() -> LocalLLMClient:
    """Create a client pointing at the local MLX server."""
    host = os.environ.get("LLM_HOST", "127.0.0.1")
    port = os.environ.get("LLM_PORT", "8080")
    return LocalLLMClient(
        base_url=f"http://{host}:{port}/v1/chat/completions",
        model=os.environ.get("LLM_MODEL", "mlx-community/Mistral-7B-Instruct-v0.3-4bit"),
        # A 4-bit 7B on an M2 can take well over a minute for a full response.
        timeout=int(os.environ.get("LLM_TIMEOUT", "300")),
    )


def build_system_prompt(target_lang: str) -> str:
    """The static instruction block. Must not vary between requests."""
    return f"""You are a {target_lang} language learning assistant that creates Anki flashcards.

You will be given a single {target_lang} word or phrase, optionally followed by its grammatical function and article in parentheses. For that word you must provide UP TO 3 (can be less) of its most common distinct senses. If senses are very similar, you MUST combine them into one. If there are fewer than 3 senses for the word, provide however many there are.

For each sense provide:
1. "sense": A short English description of the meaning (1-5 words).
2. "sentence": A simple, natural sentence in {target_lang} using this word. Do not mark the word in any way in the sentence, just use it as it would normally appear. Make sure the word is actually used in the sentence and not just tacked on at the end. The sentence MUST include the word in a natural context, and MUST be a full sentence (not a fragment).
   - For nouns, include the appropriate article (le/la/les/un/une).
   - For verbs that are reflexive or commonly used reflexively, use the reflexive form (se/s').
   - For adjectives, use the adjective in its correct form as it appears in the sentence.
   - For other words, just use the word as it appears in the sentence.
3. "hidden_text": The span of the sentence to blank out on the flashcard.

   ABSOLUTE RULES, these override everything below:
   a) hidden_text MUST contain the TARGET WORD itself, in the exact form it appears in the sentence (conjugated, agreed, or inflected as needed).
   b) hidden_text MUST appear verbatim inside "sentence".
   c) hidden_text MUST NOT be the whole sentence. Keep it as short as rule (a) allows.
   d) NEVER blank out some other noun or phrase in the sentence. The learner is studying the target word, so if the target word is missing from hidden_text the card is useless.

   Given those rules, include:
   - If the target word is a NOUN: its article + the noun, plus any adjective modifying it.
     Target "glace" -> sentence "Je mange une glace." -> hidden_text "une glace"
   - If the target word is a VERB: the conjugated verb (plus the reflexive pronoun if reflexive). Do NOT include its object.
     Target "emprunter" -> sentence "Je vais emprunter un livre à mon ami." -> hidden_text "emprunter"   (NOT "un livre à mon ami")
     Target "dérouler" -> sentence "Je déroule le tube." -> hidden_text "déroule"   (NOT "le tube")
   - If the target word is an ADJECTIVE: the adjective in its agreed form, and nothing else.
     Target "grande" -> sentence "La grande maison est belle." -> hidden_text "grande"
   - Otherwise: the target word exactly as it appears in the sentence.
4. "hint": A SHORT English gloss of the target word alone, 1-5 words (e.g. "to borrow", "an ice cream", "guilty"). This is NOT the sentence translation. It MUST be shorter than "translation" and MUST NOT be a full sentence.
5. "translation": The full English translation of the sentence.
6. "level": The estimated CEFR level of the word for this sense (one of: A1, A2, B1, B2, C1, C2).

Respond ONLY with valid JSON in this exact format, with no commentary and no markdown code fences:
{{"senses": [{{"sense": "...", "sentence": "...", "hidden_text": "...", "hint": "...", "translation": "...", "level": "..."}}, ...]}}
"""


def build_user_prompt(entry: WordEntry) -> str:
    """The per-request message: just the word plus any parsed context."""
    context = []
    if entry.function:
        context.append(entry.function)
    if entry.article:
        context.append(f"article: {entry.article}")

    if context:
        return f"{entry.raw} ({', '.join(context)})"
    return entry.raw


def _extract_json(content: str) -> dict:
    """Parse the model's response, tolerating code fences and stray prose.

    The local server has no schema enforcement (unlike Mistral's json_schema
    response_format), so the model may wrap or pad its JSON.
    """
    content = content.strip()

    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", content, re.DOTALL)
    if fenced:
        content = fenced.group(1).strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Fall back to the outermost {...} span.
    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end > start:
        return json.loads(content[start:end + 1])

    raise ValueError(f"No JSON object found in model response: {content[:200]!r}")


def query_senses(client: LocalLLMClient, entry: WordEntry, target_lang: str) -> list[Sense]:
    """Query the local MLX server for senses, returning Sense objects."""
    # One user message, instructions first: Mistral instruct templates reject a
    # standalone system role, and the constant prefix still caches.
    prompt = f"{build_system_prompt(target_lang)}\n\nWord: {build_user_prompt(entry)}"

    response = requests.post(
        client.base_url,
        json={
            "model": client.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.5,
            "max_tokens": 900,
        },
        timeout=client.timeout,
    )

    if not response.ok:
        # mlx_lm.server reports template/validation failures as 404 with the
        # real reason in the body, so raise_for_status() alone is misleading.
        raise RuntimeError(
            f"Local LLM server returned {response.status_code}: {response.text[:300]}"
        )

    content = response.json()["choices"][0]["message"]["content"]
    data = _extract_json(content)

    senses = []
    for s in data.get("senses", []):
        s = clean_sense(s)
        missing = [k for k in ("sense", "sentence", "hidden_text", "hint", "translation") if not s.get(k)]
        if missing:
            print(f"  Warning: skipping sense for '{entry.raw}', missing {missing}")
            continue

        # Leave the level unset rather than guessing one: it is reference-only,
        # and a fabricated CEFR level is worse than a visibly missing one.
        level = s.get("level")
        if level not in VALID_LEVELS:
            print(f"  Warning: no usable level {level!r} for '{entry.raw}', leaving it unset")
            level = None

        senses.append(Sense(
            sense_number=len(senses) + 1,
            sense_description=s["sense"],
            sentence=s["sentence"],
            hidden_text=s["hidden_text"],
            hint=s["hint"],
            cloze_sentence=_build_cloze(s["sentence"], s["hidden_text"], s["hint"]),
            translation=s["translation"],
            level=Level(value=level) if level else None,
        ))

    return senses
