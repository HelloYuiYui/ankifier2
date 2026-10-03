"""The audio filename scheme and the download's crash-safety.

store_media_file overwrites by name, so a filename collision would silently
replace the audio of a card already in Anki.
"""

import re

import pytest

from ankifier import elevenlabs_connector as el
from ankifier.settings import Settings


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
	"""Pin voice and model so the hashes don't depend on the developer's .env."""
	s = Settings(
		_env_file=None,
		elevenlabs_voice_id="voice-a",
		elevenlabs_model="model-a",
	)
	monkeypatch.setattr(el, "get_settings", lambda: s)
	return s


# ---------------------------------------------------------------------------
# sanitize_filename
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
	"raw,expected",
	[
		("Bonjour", "bonjour"),
		("Je mange une pomme", "je_mange_une_pomme"),
		("Il a brûlé le dîner", "il_a_brûlé_le_dîner"),  # \w is unicode-aware
		("what?! really...", "what_really"),
		("  padded  ", "padded"),
		("rendez-vous", "rendez-vous"),
		("?!.", ""),
	],
)
def test_sanitize_filename(raw, expected):
	assert el.sanitize_filename(raw) == expected


# ---------------------------------------------------------------------------
# audio_filename -- content addressing
# ---------------------------------------------------------------------------
def test_same_text_gives_the_same_name():
	assert el.audio_filename("Je mange") == el.audio_filename("Je mange")


def test_different_text_gives_a_different_name():
	assert el.audio_filename("Je mange") != el.audio_filename("Je bois")


def test_an_edited_sentence_gets_its_own_file():
	"""Otherwise it would overwrite the audio of the card already made from it."""
	before = el.audio_filename("Je mange une pomme", stem="manger")
	after = el.audio_filename("Je mange une poire", stem="manger")
	assert before != after


def test_the_stem_only_affects_the_readable_prefix():
	"""Two different stems for the same text share a digest but not a name."""
	a = el.audio_filename("Je mange", stem="manger")
	b = el.audio_filename("Je mange", stem="pomme")
	assert a != b
	assert a.rsplit("_", 1)[1] == b.rsplit("_", 1)[1]


def test_changing_voice_changes_the_name(monkeypatch):
	"""The file holds audio, not text, so the voice is part of its identity."""
	before = el.audio_filename("Je mange")
	monkeypatch.setattr(
		el,
		"get_settings",
		lambda: Settings(
			_env_file=None, elevenlabs_voice_id="voice-b", elevenlabs_model="model-a"
		),
	)
	assert el.audio_filename("Je mange") != before


def test_name_is_the_readable_text_then_the_hash():
	name = el.audio_filename("Je mange")
	assert re.fullmatch(r"je_mange_[0-9a-f]{10}\.mp3", name)


def test_all_punctuation_input_does_not_produce_a_leading_underscore():
	"""sanitize_filename returns "" for "?!."."""
	name = el.audio_filename("?!.", stem="?!.")
	assert name.startswith("card_")


def test_long_text_is_truncated_but_still_unique():
	long_a = "a" * 300
	long_b = "a" * 299 + "b"
	name_a, name_b = el.audio_filename(long_a), el.audio_filename(long_b)
	assert name_a != name_b  # the digest survives truncation
	assert len(name_a) < 80


# ---------------------------------------------------------------------------
# generate_audio -- reuse and crash-safety
# ---------------------------------------------------------------------------
class FakeClient:
	def __init__(self, chunks=(b"ID3", b"audio"), fail=False):
		self.chunks, self.fail, self.calls = chunks, fail, 0
		self.text_to_speech = self

	def convert(self, **kwargs):
		self.calls += 1
		if self.fail:
			raise RuntimeError("elevenlabs is down")
		return iter(self.chunks)


def test_writes_the_file(tmp_path):
	client = FakeClient()
	out = tmp_path / "a.mp3"
	el.generate_audio(client, "Je mange", out)
	assert out.read_bytes() == b"ID3audio"


def test_an_existing_file_is_reused_and_costs_no_credits(tmp_path):
	"""So the add reuses a preview's file. Safe because paths are content-addressed."""
	client = FakeClient()
	out = tmp_path / "a.mp3"
	el.generate_audio(client, "Je mange", out)
	el.generate_audio(client, "Je mange", out)
	assert client.calls == 1


def test_an_empty_file_is_not_trusted(tmp_path):
	client = FakeClient()
	out = tmp_path / "a.mp3"
	out.touch()
	el.generate_audio(client, "Je mange", out)
	assert client.calls == 1
	assert out.read_bytes() == b"ID3audio"


def test_skip_if_present_can_be_turned_off(tmp_path):
	client = FakeClient()
	out = tmp_path / "a.mp3"
	el.generate_audio(client, "Je mange", out)
	el.generate_audio(client, "Je mange", out, skip_if_present=False)
	assert client.calls == 2


def test_a_failed_download_leaves_no_file_behind(tmp_path):
	"""A truncated mp3 left at the final path would be reused forever."""
	client = FakeClient(fail=True)
	out = tmp_path / "a.mp3"
	with pytest.raises(RuntimeError):
		el.generate_audio(client, "Je mange", out)
	assert not out.exists()
	assert list(tmp_path.iterdir()) == []
