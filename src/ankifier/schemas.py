"""The wire contract: snake_case in Python, camelCase on the wire. Models accept
either spelling on input and emit camelCase.

packages/api/src/types.ts mirrors this file by hand and must change with it;
check /docs to confirm the two still agree.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from ankifier.models import CEFRLevel, Gender, PartOfSpeech

# The kinds differ only in which deck and tags they get. Keep it that way.
Kind = Literal["generated", "as_is", "manual"]

# "skipped" is a non-failure: an existing duplicate, or work not done because
# dry_run was set.
State = Literal["ok", "skipped", "error"]

# Which text ElevenLabs reads. The sound tag goes on the back field either way,
# so audio never plays before the card is turned over.
AudioSide = Literal["front", "back"]


class Base(BaseModel):
	model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------
class CardDraft(Base):
	"""One prospective Anki note: the response of /api/generate and the request
	of /api/cards/add, since the server keeps no batch state.

<<<<<<< HEAD
	Deck, tags and audio filename are deliberately absent: they are derived
	server-side, so a client cannot create a stray deck or make two cards collide
	on one audio file. `extra_tags` can only add to the derived tags.
=======
	The client holds these between generating and adding -- the server keeps no
	batch state -- so this is both the response body of /api/generate and the
	request body of /api/cards/add.

	Note what is NOT here: deck, tags and audio filename. Those are derived
<<<<<<< HEAD
	server-side from `kind`, `deck_target` and the text, so a client cannot create a stray
	deck and cannot make two cards collide on one audio file.
=======
	server-side from `kind` and from the text, so a client cannot create a stray
	deck and cannot make two cards collide on one audio file. `extra_tags` only
	adds to the derived tags; it cannot remove or replace them.
>>>>>>> main
>>>>>>> main
	"""

	# f"{source_id}#{n}". Deterministic, so regenerating a row keeps the user's
	# keep/discard choices attached.
	id: str
	# One per input line; not unique, since a line can fan out into several senses.
	source_id: str
	kind: Kind

	# The input line (or the manual front), for display only.
	word: str
	# Display ordinal within a source line; carries no identity.
	sense_number: int = 1
	sense_description: str = ""

	# What ElevenLabs reads unless audio_side is "back". Always marker-free.
	sentence: str
	# The Anki "Text" (Cloze) or "Front" (Basic) field.
	cloze_sentence: str
	# The Anki "Back Extra" / "Back" field.
	translation: str = ""

	# Generation-time artefacts, shown but not editable: they describe the
	# sentence as it was generated and go stale the moment it is edited.
	hidden_text: str = ""
	hint: str = ""

	# Optional metadata, which becomes tags.
	level: CEFRLevel | None = None
	gender: Gender | None = None
	part_of_speech: PartOfSpeech | None = None
	# Comma-separated text as typed, not a list: the UIs store each keystroke, and
	# a list would eat a comma the moment it was typed. Parsed by parse_tags().
	extra_tags: str = Field("", max_length=500)

	# "back" reads `translation` instead of `sentence`: for a card whose front is a
	# prompt to recall (a subjunctive form, say), hearing it would give the answer.
	audio_side: AudioSide = "front"

	# Names the audio file when the spoken text is unwieldy (an as-is card's
	# "word" is a whole sentence). Cosmetic; the file's identity is its content.
	audio_stem: str | None = None

	# Manual cards only; ignored for every other kind. None means the
	# configured manual deck.
	deck_target: DeckTarget | None = None


class Status(Base):
	state: State
	detail: str | None = None


class AddResult(Base):
	id: str
	audio: Status
	card: Status
	deck: str
	# Pre-encoded (the names contain accented characters); treat as opaque.
	audio_url: str | None = None


# ---------------------------------------------------------------------------
# /api/generate
# ---------------------------------------------------------------------------
class GenerateRow(Base):
	source_id: str
	text: str
	# Only these two: a manual card never reaches the model.
	kind: Literal["generated", "as_is"] = "generated"
	# 1 for the browser extension (one card, fast), 3 for the web table.
	max_senses: int = Field(3, ge=1, le=3)
	# The page sentence the word was selected from. Mistral uses it to pick the
	# sense meant there rather than the most common one. Ignored for as_is.
	context: str | None = Field(None, max_length=1000)


class GenerateRequest(Base):
	rows: list[GenerateRow]


class GenerateError(Base):
	"""A row that produced no cards. Kept apart from `cards` so it can never be
	selected and added as an empty note."""

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
	# Derives everything, but skips TTS, deck creation and note writes.
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
