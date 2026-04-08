import json
import os

from mistralai import Mistral

from ankifier.models import Sense, WordEntry


def init_client() -> Mistral:
    """Create and return a Mistral client using AI_KEY from environment."""
    api_key = os.environ.get("AI_KEY")
    if not api_key:
        raise ValueError("AI_KEY environment variable is not set")
    return Mistral(api_key=api_key)


def build_prompt(entry: WordEntry, target_lang: str) -> str:
    """Construct the user prompt for Mistral to generate senses and sentences."""
    word_desc = entry.raw
    extra_context = ""

    if entry.function:
        extra_context += f' This word is a {entry.function}.'
    if entry.article:
        extra_context += f' It is commonly used with the article(s): {entry.article}.'

    return f"""Given the {target_lang} word "{word_desc}", provide UP TO 3 (can be less) of its most common distinct senses. If senses are very similar, you MUST combine them into one. If there are less than 3 senses for the word, provide however many there are. Format should be as below:

For each sense the format should be as follows:
1. "sense": A short English description of the meaning (1-5 words).
2. "sentence": A simple, natural sentence in {target_lang} using this word. Do not mark the word in any way in the sentence, just use it as it would normally appear. Make sure the word is actually used in the sentence and not just tacked on at the end. The sentence MUST include the word in a natural context, and MUST be a full sentence (not a fragment).
   - For nouns, include the appropriate article (le/la/les/un/une).
   - For verbs that are reflexive or commonly used reflexively, use the reflexive form (se/s').
   - For adjectives, use the adjective in its correct form as it appears in the sentence.
   - For other words, just use the word as it appears in the sentence.
3. "hidden_text": The part of the sentence that should be hidden in a flashcard. This MUST include:
   - For nouns: the article + the word (e.g., "la glace", "un livre" or "du pain"). if there is an adjective, include it as well (e.g., "la grande maison", "un petit chat")
   - For reflexive verbs: the reflexive pronoun + the verb (e.g., "se promener" or "se promène")
   - For adjectives: the adjective in its correct form as it appears in the sentence
   - For other words: the word as it appears in the sentence
4. "hint": The English translation that will be shown as a hint. if there is an adjective, include it as well, if not only include the sense.
5. "translation": The full English translation of the sentence.

Respond ONLY with valid JSON in this exact format:
{{"senses": [{{"sense": "...", "sentence": "...", "hidden_text": "...", "hint": "...", "translation": "..."}}, ...]}}
"""

def _build_cloze(sentence: str, hidden_text: str, hint: str) -> str:
    """Replace the hidden_text in the sentence with Anki cloze format."""
    # Case-insensitive search for the hidden text in the sentence
    lower_sentence = sentence.lower()
    lower_hidden = hidden_text.lower()
    idx = lower_sentence.find(lower_hidden)

    if idx != -1:
        # Preserve original casing from the sentence
        original = sentence[idx:idx + len(hidden_text)]
        cloze = f"{{{{c1::{original}::{hint}}}}}"
        return sentence[:idx] + cloze + sentence[idx + len(hidden_text):]

    # Fallback: if exact match not found, prepend cloze to sentence
    return f"{{{{c1::{hidden_text}::{hint}}}}} - {sentence}"


def query_senses(client: Mistral, entry: WordEntry, target_lang: str) -> list[Sense]:
    """Query Mistral for senses and example sentences, returning Sense objects."""
    system_prompt = (
        f"You are a {target_lang} language learning assistant. "
        f"You help create Anki flashcards for {target_lang} vocabulary. "
        "Always respond in valid JSON matching the requested schema."
    )
    user_prompt = build_prompt(entry, target_lang)

    response = client.chat.complete(
        model="mistral-medium-latest",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "word_senses",
                "schema": {
                    "type": "object",
                    "properties": {
                        "senses": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "sense": {"type": "string"},
                                    "sentence": {"type": "string"},
                                    "hidden_text": {"type": "string"},
                                    "hint": {"type": "string"},
                                    "translation": {"type": "string"},
                                },
                                "required": ["sense", "sentence", "hidden_text", "hint", "translation"],
                                "additionalProperties": False,
                            },
                        },
                    },
                    "required": ["senses"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        },
    )

    content = response.choices[0].message.content
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
