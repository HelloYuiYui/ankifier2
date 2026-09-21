"""The wire contract.

snake_case in Python, camelCase on the wire. Every model accepts either spelling
on input and emits camelCase, so the TypeScript client sees idiomatic JSON and
the Python side stays idiomatic Python.

web/src/api/types.ts mirrors this file by hand. When a model here changes, that
file changes with it -- /docs is the place to check the two still agree.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ankifier.models import CEFRLevel

# What a card is and where it came from. The three kinds differ only in which
# deck and tags they get -- by the time a card is added, nothing else about them
# is distinguishable. Keep it that way.
Kind = Literal["generated", "as_is", "manual"]

# "skipped" is a non-failure: an existing duplicate, or work not done because
# dry_run was set.
State = Literal["ok", "skipped", "error"]


class Base(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------
class CardDraft(Base):
    """One prospective Anki note.

    The client holds these between generating and adding -- the server keeps no
    batch state -- so this is both the response body of /api/generate and the
    request body of /api/cards/add.

    Note what is NOT here: deck, tags and audio filename. Those are derived
    server-side from `kind` and from the text, so a client cannot create a stray
    deck and cannot make two cards collide on one audio file.
    """

    # f"{source_id}#{n}". Deterministic, so regenerating one input row produces
    # the same ids rather than orphaning the user's keep/discard choices.
    id: str
    # One per input line. A line can fan out into several senses, so this is not
    # unique across a batch.
    source_id: str
    kind: Kind

    # The input line (or the manual front), for display only.
    word: str
    # Display ordinal within a source line. Carries no identity -- it used to
    # also name the audio file and flag errors, and it does neither now.
    sense_number: int = 1
    sense_description: str = ""

    # What ElevenLabs reads. Always marker-free.
    sentence: str
    # The Anki "Text" (Cloze) or "Front" (Basic) field.
    cloze_sentence: str
    # The Anki "Back Extra" / "Back" field.
    translation: str = ""

    # Generation-time artefacts, shown but not editable: they describe the
    # sentence as it was generated and go stale the moment it is edited.
    hidden_text: str = ""
    hint: str = ""
    level: CEFRLevel | None = None

    # Names the audio file when the spoken text is unwieldy (an as-is card's
    # "word" is a whole sentence). Cosmetic; the file's identity is its content.
    audio_stem: str | None = None


class Status(Base):
    state: State
    detail: str | None = None


class AddResult(Base):
    id: str
    audio: Status
    card: Status
    deck: str
    # Fully-formed and pre-encoded -- these names contain accented characters,
    # so the client must treat it as opaque and never rebuild it.
    audio_url: str | None = None


# ---------------------------------------------------------------------------
# /api/generate
# ---------------------------------------------------------------------------
class GenerateRow(Base):
    source_id: str
    text: str
    # Only these two: a manual card never reaches the model.
    kind: Literal["generated", "as_is"] = "generated"


class GenerateRequest(Base):
    rows: list[GenerateRow]


class GenerateError(Base):
    """A row that produced no cards.

    Kept apart from `cards` rather than being a card with an error on it: an
    error row used to stay selectable, and adding one sent an empty string to
    ElevenLabs and an empty note to Anki.
    """

    source_id: str
    text: str
    message: str


class GenerateResponse(Base):
    cards: list[CardDraft] = Field(default_factory=list)
    errors: list[GenerateError] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# /api/cloze/preview
# ---------------------------------------------------------------------------
class ClozeText(Base):
    id: str
    text: str
    # Manual cards carry their hint inside the marker as [[word:hint]]; as-is
    # cards get hints positionally from Mistral instead.
    inline_hints: bool = True


class ClozePreviewRequest(Base):
    """Batched: a table of 60 rows is one request, not 60."""

    texts: list[ClozeText]


class ClozeResult(Base):
    id: str
    plain: str
    cloze: str


class ClozePreviewResponse(Base):
    results: list[ClozeResult]


# ---------------------------------------------------------------------------
# /api/cards/add
# ---------------------------------------------------------------------------
class AddRequest(Base):
    cards: list[CardDraft]
    # Runs everything except storeMediaFile and addNote. The whole path, no
    # side effects.
    dry_run: bool = False


class AddResponse(Base):
    results: list[AddResult]


# ---------------------------------------------------------------------------
# /api/audio
# ---------------------------------------------------------------------------
class AudioPreviewRequest(Base):
    text: str
    stem: str | None = None


class AudioPreviewResponse(Base):
    audio_url: str


# ---------------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------------
class AnkiStatus(Base):
    ok: bool
    version: int | None = None
    error: str | None = None


class KeyStatus(Base):
    mistral: bool
    elevenlabs: bool


class DeckConfig(Base):
    generated: str
    as_is: str
    manual: str


class HealthResponse(Base):
    """One call at boot: everything the shell needs to render itself."""

    anki: AnkiStatus
    keys: KeyStatus
    decks: DeckConfig
    target_lang: str
    # Every deck in the collection, for a deck picker. None when Anki is down --
    # distinct from an empty collection.
    anki_decks: list[str] | None = None
