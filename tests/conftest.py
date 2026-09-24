"""Keep the developer's real configuration out of the tests.

Settings reads both .env and the ambient environment, so without this a test
asserting on a default would pick up whatever is in the shell -- and a failure
diff would print the value, which for AI_KEY or ELEVEN_LABS_KEY means a real
secret in the test output.
"""

import pytest

from ankifier.settings import get_settings

_ANKIFIER_ENV = (
	"AI_KEY",
	"ELEVEN_LABS_KEY",
	"ANKICONNECT_URL",
	"ANKI_CONNECT_TIMEOUT",
	"ANKI_READ_TIMEOUT",
	"ANKI_DECK",
	"ANKI_ASIS_DECK",
	"ANKI_MANUAL_DECK",
	"ANKI_TAGS",
	"TARGET_LANG",
	"MISTRAL_MODEL",
	"MISTRAL_TIMEOUT",
	"AUDIO_DIR",
	"ELEVENLABS_VOICE_ID",
	"ELEVENLABS_MODEL",
	"ELEVENLABS_OUTPUT_FORMAT",
	"ELEVENLABS_TIMEOUT",
	"HOST",
	"PORT",
	"RELOAD",
	"CORS_ORIGINS",
)


@pytest.fixture(autouse=True)
def hermetic_settings(monkeypatch):
	for name in _ANKIFIER_ENV:
		monkeypatch.delenv(name, raising=False)
	# get_settings is lru_cached, so a Settings built during import (with the
	# real environment still in place) would otherwise be reused here.
	get_settings.cache_clear()
	yield
	get_settings.cache_clear()
