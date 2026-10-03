"""Every tunable in one place. Each field reads the upper-case environment
variable of the same name, or .env."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

Kind = str  # "generated" | "as_is" | "manual" -- see schemas.Kind


class Settings(BaseSettings):
	model_config = SettingsConfigDict(
		env_file=".env",
		env_file_encoding="utf-8",
		extra="ignore",
	)

	# --- credentials -------------------------------------------------------
	ai_key: str = ""
	eleven_labs_key: str = ""

	# --- AnkiConnect -------------------------------------------------------
	ankiconnect_url: str = "http://localhost:8765"
	anki_connect_timeout: float = 3.0
	anki_read_timeout: float = 30.0

	# --- decks and tags ----------------------------------------------------
	anki_deck: str = "French::Vocabulary"
	anki_asis_deck: str = "French::Grammar"
	anki_manual_deck: str = "French::Grammar"
	# Comma-separated. A plain string because pydantic-settings parses list
	# fields as JSON, which would reject ANKI_TAGS=a,b.
	anki_tags: str = "ankifier"

	# --- generation --------------------------------------------------------
	target_lang: str = "French"
	mistral_model: str = "ministral-14b-latest"
	mistral_timeout: float = 60.0

	# --- audio -------------------------------------------------------------
	audio_dir: Path = Path("audio")
	elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
	elevenlabs_model: str = "eleven_multilingual_v2"
	elevenlabs_output_format: str = "mp3_44100_128"
	elevenlabs_timeout: float = 120.0

	# --- server ------------------------------------------------------------
	host: str = "127.0.0.1"
	port: int = 8000
	reload: bool = False
	# Comma-separated; empty means no CORS middleware at all. Closed by default
	# because this server writes to Anki and spends API credits.
	cors_origins: str = ""

	# --- derived -----------------------------------------------------------
	@property
	def tags(self) -> list[str]:
		return [t.strip() for t in self.anki_tags.split(",") if t.strip()]

	@property
	def cors_origin_list(self) -> list[str]:
		return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

	@property
	def audio_root(self) -> Path:
		"""Resolved because it is the containment root for /api/audio/{filename}:
		on macOS "/tmp" resolves to "/private/tmp", and an unresolved root would
		fail every comparison."""
		return self.audio_dir.resolve()

	@property
	def anki_timeout(self) -> tuple[float, float]:
		return (self.anki_connect_timeout, self.anki_read_timeout)

	def deck_for(self, kind: Kind) -> str:
		return {
			"as_is": self.anki_asis_deck,
			"manual": self.anki_manual_deck,
		}.get(kind, self.anki_deck)

	def tags_for(self, kind: Kind) -> list[str]:
		"""Base tags, plus a tag marking the kind so each can be searched for."""
		tags = list(self.tags)
		extra = {"as_is": "as-is", "manual": "manual"}.get(kind)
		if extra and extra not in tags:
			tags.append(extra)
		return tags


@lru_cache
def get_settings() -> Settings:
	return Settings()
