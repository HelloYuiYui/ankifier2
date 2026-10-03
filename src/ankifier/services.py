"""Generation and card creation, with no HTTP in sight.

Plain synchronous code: the route handlers are `def`, so FastAPI runs them in a
threadpool and the blocking SDK calls never touch the event loop.

add_one() knows nothing about the batch it is part of, so making the loop
concurrent or streaming results only means changing add_cards().
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from ankifier import cloze, mistral_connector
from ankifier.anki_connector import (
	add_basic_note,
	add_cloze_note,
	check_connection,
	ensure_deck,
	store_media_file,
)
from ankifier.csv_parser import parse_line
from ankifier.elevenlabs_connector import audio_filename
from ankifier.elevenlabs_connector import generate_audio as tts
from ankifier.elevenlabs_connector import init_client as init_elevenlabs
from ankifier.schemas import (
	AddResult,
	AudioSide,
	CardDraft,
	ClozeResult,
	ClozeText,
	GenerateError,
	GenerateRow,
	Status,
)
from ankifier.settings import Settings


class PreflightError(Exception):
	"""Something that would fail every card in the batch identically.

	Raised before any side effect, so the caller can return a real HTTP status.
	"""


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------
@lru_cache
def _mistral_client():
	return mistral_connector.init_client()


@lru_cache
def _elevenlabs_client():
	return init_elevenlabs()


# ---------------------------------------------------------------------------
# Cloze preview
# ---------------------------------------------------------------------------
def render_cloze(texts: list[ClozeText]) -> list[ClozeResult]:
	results = []
	for t in texts:
		plain, cloze_text = cloze.render(t.text, inline_hints=t.inline_hints)
		results.append(ClozeResult(id=t.id, plain=plain, cloze=cloze_text))
	return results


def manual_draft(
	source_id: str,
	front: str,
	back: str,
	use_cloze: bool,
	audio_side: AudioSide = "front",
) -> CardDraft:
	"""The client normally builds these itself from /api/cloze/preview; this keeps
	the same construction available server-side and tested in one place."""
	if use_cloze:
		plain, cloze_text = cloze.render_manual(front)
	else:
		plain = cloze_text = front

	return CardDraft(
		id=f"{source_id}#1",
		source_id=source_id,
		kind="manual",
		word=front,
		sense_number=1,
		sentence=plain,
		cloze_sentence=cloze_text,
		translation=back,
		audio_side=audio_side,
		# A stem built from the raw front would carry the marker punctuation.
		# The back carries no markers, so it can name its own file.
		audio_stem=None if audio_side == "back" else plain,
	)


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def generate_batch(
	rows: list[GenerateRow], settings: Settings
) -> tuple[list[CardDraft], list[GenerateError]]:
	"""A row that fails does not stop the batch; it becomes a GenerateError."""
	client = _mistral_client()
	cards: list[CardDraft] = []
	errors: list[GenerateError] = []

	for row in rows:
		as_is = row.kind == "as_is"
		entry = parse_line(row.text, as_is=as_is)
		try:
			if as_is:
				senses = mistral_connector.translate_as_is(
					client, entry, settings.target_lang
				)
			else:
				senses = mistral_connector.query_senses(
					client,
					entry,
					settings.target_lang,
					max_senses=row.max_senses,
					context=row.context,
				)
		except Exception as e:
			errors.append(
				GenerateError(source_id=row.source_id, text=row.text, message=str(e))
			)
			continue

		if not senses:
			errors.append(
				GenerateError(
					source_id=row.source_id,
					text=row.text,
					message="No senses returned",
				)
			)
			continue

		for n, sense in enumerate(senses, start=1):
			cards.append(
				CardDraft(
					id=f"{row.source_id}#{n}",
					source_id=row.source_id,
					kind=row.kind,
					word=entry.raw,
					sense_number=sense.sense_number,
					sense_description=sense.sense_description,
					sentence=sense.sentence,
					cloze_sentence=sense.cloze_sentence,
					hidden_text=sense.hidden_text,
					hint=sense.hint,
					translation=sense.translation,
					level=sense.level,
					gender=sense.gender,
					part_of_speech=sense.part_of_speech,
				)
			)

	return cards, errors


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------
def spoken_text(card: CardDraft) -> tuple[str, str | None]:
	"""The text ElevenLabs reads for this card, and the stem that names its file.

	This does not decide where the sound tag goes: it is always on the back field.
	"""
	if card.audio_side == "back":
		# Not card.word: that is the front, which this audio does not contain.
		return card.translation, card.audio_stem
	return card.sentence, card.audio_stem or card.word


def audio_path(text: str, stem: str | None, settings: Settings) -> Path:
	return settings.audio_root / audio_filename(text, stem)


def audio_url(filename: str) -> str:
	"""Pre-encoded, because these names contain accented characters."""
	return f"/api/audio/{quote(filename)}"


def synthesize(text: str, stem: str | None, settings: Settings) -> Path:
	settings.audio_root.mkdir(parents=True, exist_ok=True)
	path = audio_path(text, stem, settings)
	tts(_elevenlabs_client(), text, path)
	return path


# ---------------------------------------------------------------------------
# Adding to Anki
# ---------------------------------------------------------------------------
def preflight(
	cards: list[CardDraft], settings: Settings, *, dry_run: bool = False
) -> None:
	if not cards:
		raise PreflightError("No cards to add")
	if not settings.eleven_labs_key:
		raise PreflightError("ELEVEN_LABS_KEY is not set")
	if not check_connection():
		raise PreflightError("Anki is not reachable -- is it running with AnkiConnect?")

	if dry_run:
		# createDeck writes to the collection, which a dry run must not touch.
		return

	try:
		settings.audio_root.mkdir(parents=True, exist_ok=True)
	except OSError as e:
		raise PreflightError(f"Audio directory is not writable: {e}") from e

	for deck in {settings.deck_for(c.kind) for c in cards}:
		ensure_deck(deck)


def parse_tags(text: str) -> list[str]:
	"""Anki separates tags with spaces, so "past tense, food" becomes
	["past-tense", "food"] rather than three tags."""
	tags = ("-".join(part.split()) for part in text.split(","))
	return list(dict.fromkeys(t for t in tags if t))


def note_tags(card: CardDraft, settings: Settings) -> list[str]:
	"""The derived tags -- kind, CEFR level, part of speech, a noun's gender --
	then the user's own."""
	tags = settings.tags_for(card.kind)
	if card.level:
		tags.append(card.level)
	if card.part_of_speech:
		tags.append(card.part_of_speech)
	if card.gender:
		tags.append(card.gender)
	# A user tag can add to the derived ones but not remove them.
	return list(dict.fromkeys([*tags, *parse_tags(card.extra_tags)]))


def add_one(card: CardDraft, settings: Settings, *, dry_run: bool = False) -> AddResult:
	deck = settings.deck_for(card.kind)
	text, stem = spoken_text(card)
	filename = audio_filename(text, stem)
	path = settings.audio_root / filename
	note_type = "Cloze" if "{{c" in card.cloze_sentence else "Basic"

	# ElevenLabs rejects "", so an empty side skips the audio but keeps the card.
	nothing_to_read = Status(
		state="skipped", detail=f"nothing to read -- the {card.audio_side} is empty"
	)
	speakable = bool(text.strip())

	if dry_run:
		# The deck, filename and note type are all settled by now, and they are
		# what a dry run is for checking. No credits spent, nothing written.
		return AddResult(
			id=card.id,
			audio=(
				Status(state="skipped", detail=f"dry run -- would write {filename}")
				if speakable
				else nothing_to_read
			),
			card=Status(
				state="skipped", detail=f"dry run -- would add a {note_type} note"
			),
			deck=deck,
		)

	if not speakable:
		audio = nothing_to_read
	else:
		audio = Status(state="ok")
		try:
			tts(_elevenlabs_client(), text, path)
		except Exception as e:
			audio = Status(state="error", detail=str(e))

	audio_ok = audio.state == "ok"
	status = Status(state="ok")
	try:
		if audio_ok:
			store_media_file(filename, str(path))
		if note_type == "Cloze":
			add_cloze_note(
				deck_name=deck,
				cloze_text=card.cloze_sentence,
				back_extra=card.translation,
				audio_filename=filename if audio_ok else None,
				tags=note_tags(card, settings),
			)
		else:
			# Anki rejects a Cloze note with zero deletions.
			add_basic_note(
				deck_name=deck,
				front=card.sentence,
				back=card.translation,
				audio_filename=filename if audio_ok else None,
				tags=note_tags(card, settings),
			)
	except RuntimeError as e:
		if "duplicate" in str(e).lower():
			status = Status(state="skipped", detail="duplicate")
		else:
			status = Status(state="error", detail=str(e))
	except Exception as e:
		status = Status(state="error", detail=str(e))

	return AddResult(
		id=card.id,
		audio=audio,
		card=status,
		deck=deck,
		audio_url=audio_url(filename) if audio_ok else None,
	)


def add_cards(
	cards: list[CardDraft], settings: Settings, *, dry_run: bool = False
) -> list[AddResult]:
	preflight(cards, settings, dry_run=dry_run)
	return [add_one(card, settings, dry_run=dry_run) for card in cards]
