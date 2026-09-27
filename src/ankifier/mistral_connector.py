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
	Level,
	PartOfSpeech,
	Sense,
	WordEntry,
)
from ankifier.settings import get_settings


def init_client() -> Mistral:
	"""Create and return a Mistral client using AI_KEY."""
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
	"""Construct the user prompt for Mistral to generate senses and sentences.

	max_senses=1 is the browser extension: one card, and -- when the page
	sentence is known -- the sense the word has there, not its most common one.
	"""
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
		# The page sentence only picks the sense. Copying it would put a long,
		# hard article sentence on the card instead of a simple one.
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


# What people actually type in "promener (verb)", in English or French.
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


def part_of_speech_from_function(function: str | None) -> PartOfSpeech | None:
	"""The user's own "(verb)" annotation, if it names one of the four classes."""
	return _FUNCTION_ALIASES.get((function or "").strip().lower())


def clean_sense(s: dict) -> dict:
	"""Strip markdown emphasis from a raw sense dict's string fields.

	Models keep marking the target word as **this** despite the prompt telling
	them not to, so remove the asterisks here instead. Must run before
	_build_cloze: a starred hidden_text would otherwise fail to match the
	sentence and hit the fallback path.
	"""
	return {k: v.replace("*", "") if isinstance(v, str) else v for k, v in s.items()}


def _build_cloze(sentence: str, hidden_text: str, hint: str) -> str:
	"""Replace the hidden_text in the sentence with Anki cloze format."""
	# Case-insensitive search for the hidden text in the sentence
	lower_sentence = sentence.lower()
	lower_hidden = hidden_text.lower()
	idx = lower_sentence.find(lower_hidden)

	if idx != -1:
		# Preserve original casing from the sentence
		original = sentence[idx : idx + len(hidden_text)]
		cloze = f"{{{{c1::{original}::{hint}}}}}"
		return sentence[:idx] + cloze + sentence[idx + len(hidden_text) :]

	# Fallback: if exact match not found, prepend cloze to sentence
	return f"{{{{c1::{hidden_text}::{hint}}}}} - {sentence}"


def query_senses(
	client: Mistral,
	entry: WordEntry,
	target_lang: str,
	*,
	max_senses: int = 3,
	context: str | None = None,
) -> list[Sense]:
	"""Query Mistral for senses and example sentences, returning Sense objects."""
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

	# Sliced rather than trusted: the prompt asks for at most max_senses, but
	# nothing in strict json_schema mode enforces an array length, and a caller
	# that asked for one card must get one.
	# A part of speech the user wrote down beats the model's. It is the only
	# source here that cannot be wrong about which word class they meant.
	user_pos = part_of_speech_from_function(entry.function)
	senses = []
	for i, s in enumerate(data.get("senses", [])[:max_senses], start=1):
		s = clean_sense(s)
		sentence = s["sentence"]
		hidden_text = s["hidden_text"]
		hint = s["hint"]
		cloze_sentence = _build_cloze(sentence, hidden_text, hint)
		# The json_schema makes level required, but don't invent one if it is
		# ever absent -- the UI shows a missing level rather than a guess.
		level = s.get("level")
		gender = s.get("gender")
		pos = s.get("part_of_speech")
		# "other" (a function word) and anything unexpected both become None.
		part_of_speech = user_pos or (pos if pos in VALID_PARTS_OF_SPEECH else None)
		# The two fields come from one answer but can still disagree. A verb
		# tagged "feminine" is the worse error, so only a noun keeps a gender.
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
				level=Level(value=level) if level in VALID_LEVELS else None,
				# "none" (not a noun) and anything unexpected both become None.
				gender=gender if gender in VALID_GENDERS else None,
				part_of_speech=part_of_speech,
			)
		)

	return senses


# ---------------------------------------------------------------------------
# "As is" mode: the user supplies the finished text, we only translate it.
# ---------------------------------------------------------------------------

# The marker syntax itself lives in ankifier.cloze, which the manual card
# path also uses without making any API call. Re-exported here so existing
# callers (and tests) keep working.


def build_as_is_prompt(plain_text: str, parts: list[str], target_lang: str) -> str:
	"""Construct the translate-only prompt for a single as-is text."""
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
	"""Translate an as-is text and cloze its -...- parts.

	Returns a single-element list so callers can treat it like query_senses.
	"""
	raw = entry.raw
	parts = extract_marked_parts(raw)
	# plain_text is marker-free: it is all Mistral and ElevenLabs ever see, so
	# the model cannot echo a marker back and the TTS never reads a hyphen.
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
			# CEFR levels describe a word sense; an as-is text has none to report.
			level=None,
		)
	]
