"""Internal dataclasses used between the connectors and services.

Not the wire contract -- that is schemas.py. These exist because the connectors
predate the API and still speak in Sense/WordEntry; services.py is where a Sense
becomes a CardDraft.
"""

from dataclasses import dataclass
from typing import Literal, get_args

CEFRLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
VALID_LEVELS = frozenset(get_args(CEFRLevel))

# Grammatical gender, for nouns only. Every other word class has none.
Gender = Literal["masculine", "feminine"]
VALID_GENDERS = frozenset(get_args(Gender))

# Only the four open word classes. Pronouns, articles, prepositions and the
# like get no part of speech at all, so they get no tag either.
PartOfSpeech = Literal["noun", "verb", "adjective", "adverb"]
VALID_PARTS_OF_SPEECH = frozenset(get_args(PartOfSpeech))


@dataclass
class WordEntry:
	"""Parsed from one line of the CSV."""

	raw: str
	word: str
	article: str | None = None
	function: str | None = None
	# "as is": the raw text is the card itself. No sense generation happens --
	# the model only translates, and any -...- markers become the clozes.
	as_is: bool = False


@dataclass
class Level:
	value: CEFRLevel


@dataclass
class Sense:
	"""One sense of a word, as returned by Mistral."""

	sense_number: int
	sense_description: str
	sentence: str
	hidden_text: str
	hint: str
	cloze_sentence: str
	translation: str
	# Optional: the model does not always return a level, and it is for
	# reference only (not used on the Anki card), so absent beats invented.
	level: Level | None = None
	# Nouns only. None for everything else, and for an as-is text.
	gender: Gender | None = None
	# None for function words, and for an as-is text.
	part_of_speech: PartOfSpeech | None = None
