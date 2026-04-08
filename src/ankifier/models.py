from dataclasses import dataclass, field


@dataclass
class WordEntry:
    """Parsed from one line of the CSV."""
    raw: str
    word: str
    article: str | None = None
    function: str | None = None


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
