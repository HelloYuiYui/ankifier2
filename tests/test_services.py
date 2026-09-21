"""Tests for services.py, with every connector faked.

The decisions pinned here are the ones web.py made inline and that a regression
would be invisible: which deck a card lands in, which note type it becomes, that
a failed audio still creates a card, and that a duplicate is a skip rather than
an error.
"""

import pytest

from ankifier import services
from ankifier.models import Level, Sense
from ankifier.schemas import CardDraft, ClozeText, GenerateRow
from ankifier.settings import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        ai_key="test-key",
        eleven_labs_key="test-key",
        audio_dir=tmp_path / "audio",
    )


class FakeAnki:
    """Records what would have been sent to AnkiConnect."""

    def __init__(self, *, connected=True, fail_with=None):
        self.connected, self.fail_with = connected, fail_with
        self.decks, self.media, self.notes = [], [], []

    def check_connection(self):
        return self.connected

    def ensure_deck(self, deck):
        self.decks.append(deck)

    def store_media_file(self, filename, path):
        self.media.append(filename)

    def _add(self, kind, **kw):
        if self.fail_with:
            raise self.fail_with
        self.notes.append({"type": kind, **kw})
        return len(self.notes)

    def add_cloze_note(self, **kw):
        return self._add("Cloze", **kw)

    def add_basic_note(self, **kw):
        return self._add("Basic", **kw)


@pytest.fixture
def anki(monkeypatch):
    fake = FakeAnki()
    for name in (
        "check_connection", "ensure_deck", "store_media_file",
        "add_cloze_note", "add_basic_note",
    ):
        monkeypatch.setattr(services, name, getattr(fake, name))
    return fake


@pytest.fixture
def tts(monkeypatch):
    """Fake TTS that records calls and writes a plausible file."""
    calls = []

    def fake_tts(client, text, path, **kw):
        calls.append(text)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"ID3fake")
        return str(path)

    monkeypatch.setattr(services, "tts", fake_tts)
    monkeypatch.setattr(services, "_elevenlabs_client", lambda: object())
    return calls


def draft(**overrides) -> CardDraft:
    base = dict(
        id="a#1", source_id="a", kind="generated", word="manger",
        sentence="Je mange une pomme",
        cloze_sentence="Je {{c1::mange::eat}} une pomme",
        translation="I eat an apple",
    )
    return CardDraft(**{**base, **overrides})


# ---------------------------------------------------------------------------
# Cloze preview
# ---------------------------------------------------------------------------
def test_render_cloze_is_batched_and_keeps_ids():
    results = services.render_cloze([
        ClozeText(id="x", text="Je [[mange:eat]] ici"),
        ClozeText(id="y", text="rien ici"),
    ])
    assert [r.id for r in results] == ["x", "y"]
    assert results[0].plain == "Je mange ici"
    assert results[0].cloze == "Je {{c1::mange::eat}} ici"
    assert results[1].plain == results[1].cloze == "rien ici"


def test_render_cloze_positional_mode_does_not_split_on_the_colon():
    """as-is cards take hints from Mistral, so a colon is just text."""
    (result,) = services.render_cloze(
        [ClozeText(id="x", text="Je [[mange:eat]] ici", inline_hints=False)]
    )
    assert result.plain == "Je mange:eat ici"


# ---------------------------------------------------------------------------
# manual_draft
# ---------------------------------------------------------------------------
def test_manual_draft_with_cloze():
    d = services.manual_draft("m1", "Il faut que tu [[sois:etre]] la", "You must be there", True)
    assert d.kind == "manual"
    assert d.id == "m1#1"
    assert d.sentence == "Il faut que tu sois la"       # spoken, marker-free
    assert d.cloze_sentence == "Il faut que tu {{c1::sois::etre}} la"
    assert d.translation == "You must be there"
    # The stem must not carry marker punctuation into the filename.
    assert d.audio_stem == "Il faut que tu sois la"


def test_manual_draft_without_cloze_takes_the_front_literally():
    d = services.manual_draft("m1", "bonjour [[x]]", "hello", False)
    assert d.sentence == d.cloze_sentence == "bonjour [[x]]"


# ---------------------------------------------------------------------------
# generate_batch
# ---------------------------------------------------------------------------
def sense(n=1, **kw):
    base = dict(
        sense_number=n, sense_description="to eat", sentence="Je mange",
        hidden_text="mange", hint="eat",
        cloze_sentence="Je {{c1::mange::eat}}", translation="I eat",
        level=Level(value="A1"),
    )
    return Sense(**{**base, **kw})


def test_generate_batch_fans_one_row_into_several_cards(monkeypatch, settings):
    monkeypatch.setattr(services, "_mistral_client", lambda: object())
    monkeypatch.setattr(
        services.mistral_connector, "query_senses",
        lambda c, e, lang: [sense(1), sense(2), sense(3)],
    )
    cards, errors = services.generate_batch(
        [GenerateRow(source_id="a", text="manger")], settings
    )
    assert errors == []
    # Ids are unique per card but share the source row.
    assert [c.id for c in cards] == ["a#1", "a#2", "a#3"]
    assert {c.source_id for c in cards} == {"a"}


def test_generate_batch_keeps_submission_order(monkeypatch, settings):
    monkeypatch.setattr(services, "_mistral_client", lambda: object())
    monkeypatch.setattr(
        services.mistral_connector, "query_senses", lambda c, e, lang: [sense()],
    )
    rows = [GenerateRow(source_id=f"r{i}", text=f"w{i}") for i in range(5)]
    cards, _ = services.generate_batch(rows, settings)
    assert [c.source_id for c in cards] == ["r0", "r1", "r2", "r3", "r4"]


def test_a_failing_row_becomes_an_error_and_does_not_stop_the_batch(
    monkeypatch, settings
):
    monkeypatch.setattr(services, "_mistral_client", lambda: object())

    def flaky(client, entry, lang):
        if entry.raw == "bad":
            raise RuntimeError("model exploded")
        return [sense()]

    monkeypatch.setattr(services.mistral_connector, "query_senses", flaky)
    cards, errors = services.generate_batch(
        [
            GenerateRow(source_id="a", text="good"),
            GenerateRow(source_id="b", text="bad"),
            GenerateRow(source_id="c", text="good"),
        ],
        settings,
    )
    assert [c.source_id for c in cards] == ["a", "c"]
    assert len(errors) == 1
    assert errors[0].source_id == "b"
    assert "model exploded" in errors[0].message


def test_an_empty_sense_list_is_an_error_not_a_blank_card(monkeypatch, settings):
    """A blank card used to be addable, which sent an empty note to Anki."""
    monkeypatch.setattr(services, "_mistral_client", lambda: object())
    monkeypatch.setattr(services.mistral_connector, "query_senses", lambda c, e, l: [])
    cards, errors = services.generate_batch(
        [GenerateRow(source_id="a", text="manger")], settings
    )
    assert cards == []
    assert len(errors) == 1


def test_as_is_rows_use_the_translate_only_path(monkeypatch, settings):
    monkeypatch.setattr(services, "_mistral_client", lambda: object())
    used = []
    monkeypatch.setattr(
        services.mistral_connector, "query_senses",
        lambda c, e, l: used.append("query") or [sense()],
    )
    monkeypatch.setattr(
        services.mistral_connector, "translate_as_is",
        lambda c, e, l: used.append("as_is") or [sense()],
    )
    services.generate_batch(
        [
            GenerateRow(source_id="a", text="manger", kind="generated"),
            GenerateRow(source_id="b", text="Il faut [[sois]]", kind="as_is"),
        ],
        settings,
    )
    assert used == ["query", "as_is"]


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------
def test_preflight_rejects_an_empty_batch(settings, anki):
    with pytest.raises(services.PreflightError):
        services.preflight([], settings)


def test_preflight_rejects_a_missing_key(tmp_path, anki):
    s = Settings(_env_file=None, eleven_labs_key="", audio_dir=tmp_path)
    with pytest.raises(services.PreflightError, match="ELEVEN_LABS_KEY"):
        services.preflight([draft()], s)


def test_preflight_rejects_an_unreachable_anki(settings, anki, monkeypatch):
    monkeypatch.setattr(services, "check_connection", lambda: False)
    with pytest.raises(services.PreflightError, match="not reachable"):
        services.preflight([draft()], settings)


def test_preflight_creates_only_the_decks_the_batch_needs(settings, anki):
    services.preflight(
        [draft(kind="generated"), draft(kind="manual"), draft(kind="generated")],
        settings,
    )
    assert sorted(anki.decks) == ["French::Manual", "French::Vocabulary"]


# ---------------------------------------------------------------------------
# add_one -- deck, note type, and failure handling
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "kind,deck,tag",
    [
        ("generated", "French::Vocabulary", None),
        ("as_is", "French::Grammar", "as-is"),
        ("manual", "French::Manual", "manual"),
    ],
)
def test_each_kind_lands_in_its_own_deck_with_its_marker_tag(
    settings, anki, tts, kind, deck, tag
):
    result = services.add_one(draft(kind=kind), settings)
    assert result.card.state == "ok"
    assert result.deck == deck
    assert anki.notes[0]["deck_name"] == deck
    assert "ankifier" in anki.notes[0]["tags"]
    if tag:
        assert tag in anki.notes[0]["tags"]


def test_a_cloze_sentence_becomes_a_cloze_note(settings, anki, tts):
    services.add_one(draft(cloze_sentence="Je {{c1::mange}} ici"), settings)
    assert anki.notes[0]["type"] == "Cloze"


def test_text_with_no_deletion_becomes_a_basic_note(settings, anki, tts):
    """Anki rejects a Cloze note with zero deletions."""
    services.add_one(
        draft(sentence="Bonjour", cloze_sentence="Bonjour", translation="Hello"),
        settings,
    )
    assert anki.notes[0]["type"] == "Basic"
    assert anki.notes[0]["front"] == "Bonjour"
    assert anki.notes[0]["back"] == "Hello"


def test_audio_is_generated_from_the_spoken_sentence_not_the_cloze(settings, anki, tts):
    services.add_one(draft(), settings)
    assert tts == ["Je mange une pomme"]


def test_a_failed_audio_still_creates_the_card(settings, anki, monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("elevenlabs down")

    monkeypatch.setattr(services, "tts", boom)
    monkeypatch.setattr(services, "_elevenlabs_client", lambda: object())

    result = services.add_one(draft(), settings)
    assert result.audio.state == "error"
    assert "elevenlabs down" in result.audio.detail
    assert result.card.state == "ok"          # non-fatal, as it has always been
    assert result.audio_url is None
    assert anki.media == []                   # nothing to store
    assert anki.notes[0]["audio_filename"] is None


def test_a_duplicate_is_a_skip_not_an_error(settings, tts, monkeypatch):
    fake = FakeAnki(fail_with=RuntimeError("AnkiConnect error: cannot create note because it is a duplicate"))
    for name in ("check_connection", "ensure_deck", "store_media_file",
                 "add_cloze_note", "add_basic_note"):
        monkeypatch.setattr(services, name, getattr(fake, name))

    result = services.add_one(draft(), settings)
    assert result.card.state == "skipped"
    assert result.card.detail == "duplicate"


def test_any_other_anki_failure_is_an_error(settings, tts, monkeypatch):
    fake = FakeAnki(fail_with=RuntimeError("AnkiConnect error: deck not found"))
    for name in ("check_connection", "ensure_deck", "store_media_file",
                 "add_cloze_note", "add_basic_note"):
        monkeypatch.setattr(services, name, getattr(fake, name))

    result = services.add_one(draft(), settings)
    assert result.card.state == "error"
    assert "deck not found" in result.card.detail


def test_audio_url_is_returned(settings, anki, tts):
    result = services.add_one(draft(), settings)
    assert result.audio_url == f"/api/audio/{anki.media[0]}"
    assert result.audio_url.startswith("/api/audio/ankifier_")


def test_an_accented_filename_is_percent_encoded_in_the_url(settings, anki, tts):
    """sanitize_filename keeps accents (\\w is unicode-aware), so the URL has to
    be encoded server-side -- the client treats it as opaque."""
    result = services.add_one(
        draft(sentence="Il a brûlé le dîner", audio_stem="brûlé le dîner"), settings
    )
    assert "%" in result.audio_url
    assert " " not in result.audio_url


def test_two_cards_with_different_sentences_get_different_audio_files(
    settings, anki, tts
):
    a = services.add_one(draft(id="a#1", sentence="Je mange"), settings)
    b = services.add_one(draft(id="b#1", sentence="Je bois"), settings)
    assert a.audio_url != b.audio_url


# ---------------------------------------------------------------------------
# dry run
# ---------------------------------------------------------------------------
def test_dry_run_writes_nothing_and_spends_nothing(settings, anki, tts):
    results = services.add_cards([draft(), draft(id="b#1")], settings, dry_run=True)
    assert [r.card.state for r in results] == ["skipped", "skipped"]
    assert [r.audio.state for r in results] == ["skipped", "skipped"]
    assert anki.notes == []
    assert anki.media == []
    assert tts == []          # no credits spent


def test_dry_run_still_reports_the_deck_and_note_type(settings, anki, tts):
    (cloze_result,) = services.add_cards([draft(kind="as_is")], settings, dry_run=True)
    assert cloze_result.deck == "French::Grammar"
    assert "Cloze" in cloze_result.card.detail

    (basic_result,) = services.add_cards(
        [draft(cloze_sentence="Bonjour")], settings, dry_run=True
    )
    assert "Basic" in basic_result.card.detail


def test_dry_run_still_runs_preflight(settings, anki, monkeypatch):
    monkeypatch.setattr(services, "check_connection", lambda: False)
    with pytest.raises(services.PreflightError):
        services.add_cards([draft()], settings, dry_run=True)


def test_dry_run_does_not_create_decks(settings, anki, tts):
    """createDeck is a write. A dry run must leave the collection untouched."""
    services.add_cards([draft(kind="manual")], settings, dry_run=True)
    assert anki.decks == []


def test_a_real_run_does_create_decks(settings, anki, tts):
    services.add_cards([draft(kind="manual")], settings)
    assert anki.decks == ["French::Manual"]


# ---------------------------------------------------------------------------
# add_cards
# ---------------------------------------------------------------------------
def test_add_cards_returns_one_result_per_card_in_order(settings, anki, tts):
    cards = [draft(id=f"c{i}#1", sentence=f"phrase {i}") for i in range(4)]
    results = services.add_cards(cards, settings)
    assert [r.id for r in results] == ["c0#1", "c1#1", "c2#1", "c3#1"]
    assert len(anki.notes) == 4
