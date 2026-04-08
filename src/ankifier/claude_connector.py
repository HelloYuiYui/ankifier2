import json
import os

import anthropic

from ankifier.models import Sense, WordEntry
from ankifier.mistral_connector import _build_cloze, build_prompt


def init_client() -> anthropic.Anthropic:
    """Create and return an Anthropic client using CLAUDE_API_KEY from environment."""
    api_key = os.environ.get("CLAUDE_API_KEY")
    if not api_key:
        raise ValueError("CLAUDE_API_KEY environment variable is not set")
    return anthropic.Anthropic(api_key=api_key)


def query_senses(client: anthropic.Anthropic, entry: WordEntry, target_lang: str) -> list[Sense]:
    """Query Claude for senses and example sentences, returning Sense objects."""
    system_prompt = (
        f"You are a {target_lang} language learning assistant. "
        f"You help create Anki flashcards for {target_lang} vocabulary. "
        "Always respond in valid JSON matching the requested schema."
    )
    user_prompt = build_prompt(entry, target_lang)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_prompt},
        ],
    )

    content = response.content[0].text
    data = json.loads(content)

    senses = []
    for i, s in enumerate(data.get("senses", []), start=1):
        sentence = s["sentence"]
        hidden_text = s["hidden_text"]
        hint = s["hint"]
        cloze_sentence = _build_cloze(sentence, hidden_text, hint)

        senses.append(Sense(
            sense_number=i,
            sense_description=s["sense"],
            sentence=sentence,
            hidden_text=hidden_text,
            hint=hint,
            cloze_sentence=cloze_sentence,
            translation=s["translation"],
        ))

    return senses
