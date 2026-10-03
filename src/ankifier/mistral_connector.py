import json

from mistralai import Mistral

from ankifier.cloze import (
	extract_marked_parts,
	render_as_is,
)
from ankifier.models import (
	VALID_GENDERS,
	VALID_LEVELS,
	VALID_PARTS_OF_SPEECH,
	PartOfSpeech,
	Sense,
	WordEntry,
)
from ankifier.settings import get_settings


def init_client() -> Mistral:
	settings = get_settings()
	if not settings.ai_key:
		raise ValueError("AI_KEY environment variable is not set")
	return Mistral(
		api_key=settings.ai_key,
		timeout_ms=int(settings.mistral_timeout * 1000),
	)


def build_prompt(
	entry: WordEntry,
	target_lang: str,
	*,
	max_senses: int = 3,
	context: str | None = None,
) -> str:
	"""max_senses=1 is the browser extension: one card, with the sense the word has
	in `context` when given, otherwise its most common one."""
	word_desc = entry.raw
	extra_context = ""

	if entry.function:
		extra_context += f" This word is a {entry.function}."
	if entry.article:
		extra_context += f" It is commonly used with the article(s): {entry.article}."

	if max_senses == 1:
		if context:
			which = (
				f' It appears in this sentence: "{context}". Provide exactly ONE '
				"sense: the meaning the word has in that sentence."
			)
		else:
			which = " Provide exactly ONE sense: its most common meaning."
		# The page sentence only picks the sense; copying it would put a long, hard
		# sentence on the card.
		return (
			f'Given the {target_lang} word "{word_desc}",{extra_context}{which} '
			"Write a NEW simple example sentence for it; do not reuse the sentence "
			"above. Format should be as below:"
		)

	return (
		f'Given the {target_lang} word "{word_desc}",{extra_context} provide UP TO 3 '
		"(can be less) of its most common distinct senses. If senses are similar, "
		"you MUST combine them into one. If there are less than 3 senses for the "
		"word, provide however many there are, DO NOT pad the list. Format should "
		"be as below:"
	)


_FUNCTION_ALIASES: dict[str, PartOfSpeech] = {
	"n": "noun",
	"noun": "noun",
	"nom": "noun",
	"v": "verb",
	"verb": "verb",
	"verbe": "verb",
	"adj": "adjective",
	"adjective": "adjective",
	"adjectif": "adjective",
	"adv": "adverb",
	"adverb": "adverb",
	"adverbe": "adverb",
}


# I can override PoS tags with (v) or (n).
def part_of_speech_from_function(function: str | None) -> PartOfSpeech | None:
	return _FUNCTION_ALIASES.get((function or "").strip().lower())


def clean_sense(s: dict) -> dict:
	"""Strip the **emphasis** models add despite the prompt. Must run before
	_build_cloze, or a starred hidden_text will not match the sentence."""
	return {k: v.replace("*", "") if isinstance(v, str) else v for k, v in s.items()}


def _build_cloze(sentence: str, hidden_text: str, hint: str) -> str:
	lower_sentence = sentence.lower()
	lower_hidden = hidden_text.lower()
	idx = lower_sentence.find(lower_hidden)

	if idx != -1:
		original = sentence[idx : idx + len(hidden_text)]
		cloze = f"{{{{c1::{original}::{hint}}}}}"
		return sentence[:idx] + cloze + sentence[idx + len(hidden_text) :]

	# Not found in the sentence: prepend the cloze instead.
	return f"{{{{c1::{hidden_text}::{hint}}}}} - {sentence}"


def query_senses(
	client: Mistral,
	entry: WordEntry,
	target_lang: str,
	*,
	max_senses: int = 3,
	context: str | None = None,
) -> list[Sense]:
	system_prompt = (
		f"You are a {target_lang} language learning assistant. "
		f"You help create Anki flashcards for {target_lang} vocabulary. "
		"Always respond in valid JSON matching the requested schema."
		"For each sense the format should be as follows: \
            1. 'sense': A short English description of the meaning (1-5 words). \
            2. 'sentence': A simple, natural sentence in French using this word. Do not mark the word in any way in the sentence. Just use it as it would normally appear. Make sure the word is actually used in the sentence and not just tacked on at the end. The sentence MUST include the word in a natural context, and MUST be a full sentence (not a fragment). \
                - For nouns, include the appropriate article (le/la/les/un/une).\
                - For verbs that are reflexive or commonly used reflexively, use the reflexive form (se/s'). \
                - For adjectives, use the adjective in its correct form as it appears in the sentence. \
                - For other words, just use the word as it appears in the sentence. \
            3. 'hidden_text': The part of the sentence that should be hidden in a flashcard. This MUST include: \
                - For nouns: the article + the word (e.g., 'la glace', 'un livre' or 'du pain'). if there is an adjective, include it as well (e.g., 'la grande maison', 'un petit chat') \
                - For reflexive verbs: the reflexive pronoun + the verb (e.g., 'se promener' or 'se promène') \
                - For adjectives: the adjective in its correct form as it appears in the sentence \
                - For other words: the word as it appears in the sentence \
            4. 'hint': The English translation that will be shown as a hint. if there is an adjective, include it as well, if not only include the sense. \
            5. 'translation': The full English translation of the sentence. \
            6. 'level': The estimated CEFR level of the word for this sense (one of: A1, A2, B1, B2, C1, C2). \
            7. 'gender': If the word is a noun, its grammatical gender in this sense ('masculine' or 'feminine'). For any other kind of word, 'none'. \
            8. 'part_of_speech': The part of speech of the word in this sense and sentence ('noun', 'verb', 'adjective' or 'adverb'). For any other kind of word (pronoun, article, preposition, conjunction, etc.), 'other'. \
\
            Respond ONLY with valid JSON in this exact format: \
            /{/{'senses': [/{/{'sense': '...', 'sentence': '...', 'hidden_text': '...', 'hint': '...', 'translation': '...', 'level': '...', 'gender': '...', 'part_of_speech': '...'/}/}, ...]/}/} \
        "
	)
	user_prompt = build_prompt(
		entry, target_lang, max_senses=max_senses, context=context
	)

	response = client.chat.complete(
		model=get_settings().mistral_model,
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
									"level": {
										"type": "string",
										"enum": ["A1", "A2", "B1", "B2", "C1", "C2"],
									},
									# "none" rather than optional: strict mode makes every
									# property required.
									"gender": {
										"type": "string",
										"enum": ["masculine", "feminine", "none"],
									},
									"part_of_speech": {
										"type": "string",
										"enum": [
											"noun",
											"verb",
											"adjective",
											"adverb",
											"other",
										],
									},
								},
								"required": [
									"sense",
									"sentence",
									"hidden_text",
									"hint",
									"translation",
									"level",
									"gender",
									"part_of_speech",
								],
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

	# The user's own annotation beats the model's part of speech.
	user_pos = part_of_speech_from_function(entry.function)
	senses = []
	# Sliced because strict json_schema mode cannot enforce an array length.
	for i, s in enumerate(data.get("senses", [])[:max_senses], start=1):
		s = clean_sense(s)
		sentence = s["sentence"]
		hidden_text = s["hidden_text"]
		hint = s["hint"]
		cloze_sentence = _build_cloze(sentence, hidden_text, hint)
		level = s.get("level")
		gender = s.get("gender")
		pos = s.get("part_of_speech")
		# "other" (a function word) and anything unexpected both become None.
		part_of_speech = user_pos or (pos if pos in VALID_PARTS_OF_SPEECH else None)
		if part_of_speech != "noun":
			gender = None

		senses.append(
			Sense(
				sense_number=i,
				sense_description=s["sense"],
				sentence=sentence,
				hidden_text=hidden_text,
				hint=hint,
				cloze_sentence=cloze_sentence,
				translation=s["translation"],
				level=level if level in VALID_LEVELS else None,
				gender=gender if gender in VALID_GENDERS else None,
				part_of_speech=part_of_speech,
			)
		)

	return senses


# ---------------------------------------------------------------------------
# "As is" mode: the user supplies the finished text, we only translate it.
# ---------------------------------------------------------------------------


def build_as_is_prompt(plain_text: str, parts: list[str], target_lang: str) -> str:
	prompt = (
		f"Translate the following {target_lang} text into English. "
		f"Do not rewrite, correct, expand or shorten it -- translate exactly what is given.\n\n"
		f'Text: "{plain_text}"\n'
	)
	if parts:
		listed = "\n".join(f'{i}. "{p}"' for i, p in enumerate(parts, start=1))
		prompt += (
			f"\nAlso translate each of the following fragments of that text "
			f"separately, as they are used in this text. Return them in the same "
			f"order, one entry per fragment, copying the fragment verbatim into "
			f'"source":\n{listed}\n'
		)
	return prompt


_AS_IS_SCHEMA = {
	"type": "object",
	"properties": {
		"translation": {"type": "string"},
		"parts": {
			"type": "array",
			"items": {
				"type": "object",
				"properties": {
					"source": {"type": "string"},
					"translation": {"type": "string"},
				},
				"required": ["source", "translation"],
				"additionalProperties": False,
			},
		},
	},
	"required": ["translation", "parts"],
	"additionalProperties": False,
}


def _align_part_hints(parts: list[str], returned: list[dict]) -> list[str]:
	"""Map the model's part translations onto our marker order.

	Positional first, since that is what the prompt asks for; fall back to a
	source lookup when the model drops or reorders an entry, so one bad
	fragment cannot shift every hint after it onto the wrong cloze.
	"""
	by_source = {
		(r.get("source") or "").strip().lower(): (r.get("translation") or "").strip()
		for r in returned
	}

	hints = []
	for i, part in enumerate(parts):
		candidate = returned[i] if i < len(returned) else None
		if (
			candidate
			and (candidate.get("source") or "").strip().lower() == part.lower()
		):
			hints.append((candidate.get("translation") or "").strip())
		else:
			hints.append(by_source.get(part.lower(), ""))
	return hints


def translate_as_is(client: Mistral, entry: WordEntry, target_lang: str) -> list[Sense]:
	"""Translate an as-is text and cloze its [[...]] parts.

	Returns a single-element list so callers can treat it like query_senses.
	"""
	raw = entry.raw
	parts = extract_marked_parts(raw)
	# Mistral and ElevenLabs only ever see the marker-free text, so the model
	# cannot echo a marker back.
	plain_text, _ = render_as_is(raw, [])

	system_prompt = (
		f"You are a {target_lang}-to-English translator working on Anki "
		"flashcards. Translate literally and accurately, preserving the "
		"grammatical construction of the original. Never add commentary, "
		"never generate new example sentences. Always respond in valid JSON "
		"matching the requested schema."
	)

	response = client.chat.complete(
		model=get_settings().mistral_model,
		messages=[
			{"role": "system", "content": system_prompt},
			{
				"role": "user",
				"content": build_as_is_prompt(plain_text, parts, target_lang),
			},
		],
		response_format={
			"type": "json_schema",
			"json_schema": {
				"name": "as_is_translation",
				"schema": _AS_IS_SCHEMA,
				"strict": True,
			},
		},
	)

	data = json.loads(response.choices[0].message.content)
	translation = (data.get("translation") or "").replace("*", "").strip()
	returned = [clean_sense(p) for p in data.get("parts", []) if isinstance(p, dict)]

	part_hints = _align_part_hints(parts, returned)
	_, cloze_sentence = render_as_is(raw, part_hints)

	return [
		Sense(
			sense_number=1,
			sense_description="as is",
			sentence=plain_text,
			hidden_text=" / ".join(parts),
			hint=" / ".join(h for h in part_hints if h),
			cloze_sentence=cloze_sentence,
			translation=translation,
		)
	]
