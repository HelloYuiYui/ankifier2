"""Generation and card creation, with no HTTP in sight.

Everything here is plain synchronous code -- the route handlers are `def`, so
FastAPI runs them in a threadpool and the blocking SDK calls never touch the
event loop. Both loops are serial, exactly as web.py ran them.

add_one() is deliberately per-card and stateless: it knows nothing about the
batch it is part of. That is what makes running the loop concurrently, or
streaming each result as it lands, a later change to add_cards() alone.
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
    CardDraft,
    ClozeResult,
    ClozeText,
    GenerateError,
    GenerateRow,
    Status,
)
from ankifier.settings import Settings


class PreflightError(Exception):
    """Something is wrong that would fail every card in the batch identically.

    Raised before any side effect so the caller can return a real HTTP status
    instead of a list of identical per-card errors.
    """


# ---------------------------------------------------------------------------
# Clients. Built once rather than per request: init_elevenlabs() raises when the
# key is missing, and web.py called it inside the add handler, so a missing key
# turned into a 500 for the whole batch instead of a message.
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
    """Pure string work -- no I/O, no client, no threadpool needed."""
    results = []
    for t in texts:
        plain, cloze_text = cloze.render(t.text, inline_hints=t.inline_hints)
        results.append(ClozeResult(id=t.id, plain=plain, cloze=cloze_text))
    return results


def manual_draft(source_id: str, front: str, back: str, use_cloze: bool) -> CardDraft:
    """Build a manual card without calling anything.

    The client normally builds these itself from /api/cloze/preview; this exists
    so the same construction is available server-side and tested in one place.
    """
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
        # A stem built from the raw front would carry the marker punctuation.
        audio_stem=plain,
    )


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------
def generate_batch(
    rows: list[GenerateRow], settings: Settings
) -> tuple[list[CardDraft], list[GenerateError]]:
    """Ask Mistral for senses, one row at a time.

    Serial, as it has always been: ~2s per row. A row that fails does not stop
    the batch, it becomes a GenerateError.
    """
    client = _mistral_client()
    cards: list[CardDraft] = []
    errors: list[GenerateError] = []

    for row in rows:
        as_is = row.kind == "as_is"
        entry = parse_line(row.text, as_is=as_is)
        # "As is" skips sense generation entirely: the text is already the card,
        # so the model is only asked for its translation.
        run = (
            mistral_connector.translate_as_is
            if as_is
            else mistral_connector.query_senses
        )
        try:
            senses = run(client, entry, settings.target_lang)
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
                    # One row can fan out into several cards, so the row's id
                    # alone is not unique.
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
                    level=sense.level.value if sense.level else None,
                )
            )

    return cards, errors


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------
def audio_path(text: str, stem: str | None, settings: Settings) -> Path:
    return settings.audio_root / audio_filename(text, stem)


def audio_url(filename: str) -> str:
    """Pre-encoded, because these names contain accented characters."""
    return f"/api/audio/{quote(filename)}"


def synthesize(text: str, stem: str | None, settings: Settings) -> Path:
    """Generate (or reuse) the audio for `text` and return its path."""
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
    """Check everything that would fail every card in the batch the same way.

    Runs before the first side effect, so the caller can still return a status
    code rather than a list of identical errors.
    """
    if not cards:
        raise PreflightError("No cards to add")
    if not settings.eleven_labs_key:
        raise PreflightError("ELEVEN_LABS_KEY is not set")
    if not check_connection():
        raise PreflightError("Anki is not reachable -- is it running with AnkiConnect?")

    if dry_run:
        # createDeck writes to the collection, so a dry run stops here: it must
        # leave the user's Anki exactly as it found it.
        return

    try:
        settings.audio_root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise PreflightError(f"Audio directory is not writable: {e}") from e

    # Only the decks this batch actually needs.
    for deck in {settings.deck_for(c.kind) for c in cards}:
        ensure_deck(deck)


def add_one(card: CardDraft, settings: Settings, *, dry_run: bool = False) -> AddResult:
    """Audio, then the note, for one card.

    Per-card and stateless by design. A failed audio is not fatal -- the card is
    still created, silently, exactly as before.
    """
    deck = settings.deck_for(card.kind)
    filename = audio_filename(card.sentence, card.audio_stem or card.word)
    path = settings.audio_root / filename
    note_type = "Cloze" if "{{c" in card.cloze_sentence else "Basic"

    if dry_run:
        # Everything derived, nothing spent and nothing written: the deck, the
        # filename and the note type are the things most likely to be wrong,
        # and all three are settled by this point. TTS is skipped too, so a dry
        # run costs no ElevenLabs credits either.
        return AddResult(
            id=card.id,
            audio=Status(state="skipped", detail=f"dry run -- would write {filename}"),
            card=Status(
                state="skipped", detail=f"dry run -- would add a {note_type} note"
            ),
            deck=deck,
        )

    audio = Status(state="ok")
    try:
        tts(_elevenlabs_client(), card.sentence, path)
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
                tags=[*settings.tags_for(card.kind), (str(card.level) if card.level else "unknown-level")],
            )
        else:
            # Nothing to hide -- an as-is text with no [[...]] markers. Anki
            # rejects a Cloze note with zero deletions, so it becomes a Basic.
            add_basic_note(
                deck_name=deck,
                front=card.sentence,
                back=card.translation,
                audio_filename=filename if audio_ok else None,
                tags=[*settings.tags_for(card.kind), (str(card.level) if card.level else "unknown-level")],
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
