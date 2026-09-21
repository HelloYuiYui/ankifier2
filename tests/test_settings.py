"""Tests for settings.py.

The deck and tag mappings are pinned against the behaviour of web.py's
_deck_for / _tags_for, which they replace -- a card must land in exactly the
deck it used to.

Every Settings here is built with _env_file=None so the developer's own .env
cannot change the result.
"""

import pytest

from ankifier.settings import Settings


def settings(**overrides) -> Settings:
    return Settings(_env_file=None, **overrides)


# ---------------------------------------------------------------------------
# Decks and tags -- pinned against web.py's _deck_for / _tags_for
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "kind,expected",
    [
        ("generated", "French::Vocabulary"),
        ("as_is", "French::Grammar"),
        ("manual", "French::Manual"),
    ],
)
def test_deck_for_defaults(kind, expected):
    assert settings().deck_for(kind) == expected


def test_deck_for_honours_overrides():
    s = settings(
        anki_deck="A",
        anki_asis_deck="B",
        anki_manual_deck="C",
    )
    assert (s.deck_for("generated"), s.deck_for("as_is"), s.deck_for("manual")) == (
        "A",
        "B",
        "C",
    )


def test_deck_for_unknown_kind_falls_back_to_the_vocabulary_deck():
    assert settings().deck_for("something-else") == "French::Vocabulary"


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("generated", ["ankifier"]),
        ("as_is", ["ankifier", "as-is"]),
        ("manual", ["ankifier", "manual"]),
    ],
)
def test_tags_for_defaults(kind, expected):
    assert settings().tags_for(kind) == expected


def test_tags_for_does_not_duplicate_an_already_present_marker_tag():
    s = settings(anki_tags="ankifier,as-is")
    assert s.tags_for("as_is") == ["ankifier", "as-is"]


def test_tags_for_does_not_mutate_the_base_tags():
    s = settings()
    s.tags_for("as_is")
    assert s.tags == ["ankifier"]


# ---------------------------------------------------------------------------
# Comma-separated fields
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("ankifier", ["ankifier"]),
        ("a,b,c", ["a", "b", "c"]),
        ("a, b , c", ["a", "b", "c"]),
        ("a,,b", ["a", "b"]),
        ("", []),
        ("   ", []),
    ],
)
def test_tags_splitting(raw, expected):
    assert settings(anki_tags=raw).tags == expected


def test_cors_is_empty_by_default():
    """No CORS unless explicitly configured -- this server writes to Anki."""
    assert settings().cors_origin_list == []


def test_cors_splitting():
    s = settings(cors_origins="https://a.example, https://b.example")
    assert s.cors_origin_list == ["https://a.example", "https://b.example"]


# ---------------------------------------------------------------------------
# Paths and timeouts
# ---------------------------------------------------------------------------
def test_audio_root_is_absolute():
    """It is the containment root for /api/audio/{filename}, so it must be
    resolved -- an unresolved root fails every comparison on macOS."""
    root = settings(audio_dir="audio").audio_root
    assert root.is_absolute()
    assert root.name == "audio"


def test_anki_timeout_is_a_connect_read_pair():
    s = settings(anki_connect_timeout=1.5, anki_read_timeout=45.0)
    assert s.anki_timeout == (1.5, 45.0)


def test_credentials_default_to_empty_so_the_app_can_still_boot():
    """/api/health has to be able to report a missing key, which means the
    process must start without one."""
    s = settings()
    assert s.ai_key == ""
    assert s.eleven_labs_key == ""
