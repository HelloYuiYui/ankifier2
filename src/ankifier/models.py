from dataclasses import dataclass, field
from typing import Literal, get_args

CEFRLevel = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
VALID_LEVELS = frozenset(get_args(CEFRLevel))


@dataclass
class WordEntry:
    """Parsed from one line of the CSV."""
    raw: str
    word: str
    article: str | None = None
    function: str | None = None


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


@dataclass
class WordResult:
    """Full result for one word after Mistral processing."""
    entry: WordEntry
    senses: list[Sense] = field(default_factory=list)


@dataclass
class CardData:
    """Everything needed to create one Anki card."""
    front: str
    back_text: str
    audio_path: str
    audio_filename: str
    tags: list[str] = field(default_factory=list)
