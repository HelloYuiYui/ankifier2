"""Internal types used between the connectors and services.

Not the wire contract, that is schemas.py; services.py is where a Sense
becomes a CardDraft.
"""

from dataclasses import dataclass
from typing import Literal, get_args

CEFRLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
VALID_LEVELS = frozenset(get_args(CEFRLevel))

Gender = Literal["masculine", "feminine"]
VALID_GENDERS = frozenset(get_args(Gender))

PartOfSpeech = Literal["noun", "verb", "adjective", "adverb"]
VALID_PARTS_OF_SPEECH = frozenset(get_args(PartOfSpeech))


@dataclass
class WordEntry:
	raw: str
	word: str
	article: str | None = None
	function: str | None = None
	as_is: bool = False


@dataclass
class Sense:
	sense_number: int
	sense_description: str
	sentence: str
	hidden_text: str
	hint: str
	cloze_sentence: str
	translation: str
	level: CEFRLevel | None = None
	gender: Gender | None = None
	part_of_speech: PartOfSpeech | None = None
