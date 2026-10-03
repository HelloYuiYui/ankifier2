import hashlib
import re
from pathlib import Path

from elevenlabs import ElevenLabs

from ankifier.settings import get_settings


def init_client() -> ElevenLabs:
	settings = get_settings()
	if not settings.eleven_labs_key:
		raise ValueError("ELEVEN_LABS_KEY environment variable is not set")
	return ElevenLabs(
		api_key=settings.eleven_labs_key, timeout=settings.elevenlabs_timeout
	)


def sanitize_filename(text: str) -> str:
	text = text.lower().strip()
	text = re.sub(r"[^\w\s-]", "", text)
	text = re.sub(r"[\s]+", "_", text)
	return text


def audio_filename(text: str, stem: str | None = None) -> str:
	"""Content-addressed filename for the audio of `text`.

	Hashed from the spoken text (plus voice and model, which change the audio), so
	the same text reuses one file and an edited sentence never overwrites another
	card's audio in Anki. The readable part is only for finding a file by eye.
	"""
	settings = get_settings()
	digest = hashlib.sha1(
		f"{settings.elevenlabs_voice_id}|{settings.elevenlabs_model}|{text}".encode()
	).hexdigest()[:10]
	# sanitize_filename returns "" for all-punctuation input.
	safe = sanitize_filename(stem or text)[:40] or "card"
	return f"{safe}_{digest}.mp3"


def generate_audio(
	client: ElevenLabs,
	text: str,
	output_path: str | Path,
	*,
	skip_if_present: bool = True,
) -> str:
	"""Generate TTS audio for `text` and save it to output_path.

	The path is content-addressed, so an existing file is already this audio and
	is reused for free (a preview's file is reused by the later add).

	Downloads to a .part file renamed once complete, so an interrupted run never
	leaves a truncated mp3 that would later be mistaken for a finished one.
	"""
	settings = get_settings()
	path = Path(output_path)

	if skip_if_present and path.is_file() and path.stat().st_size > 0:
		return str(path)

	audio_iterator = client.text_to_speech.convert(
		text=text,
		voice_id=settings.elevenlabs_voice_id,
		model_id=settings.elevenlabs_model,
		output_format=settings.elevenlabs_output_format,
	)

	partial = path.with_name(path.name + ".part")
	try:
		with open(partial, "wb") as f:
			for chunk in audio_iterator:
				f.write(chunk)
		partial.replace(path)
	finally:
		partial.unlink(missing_ok=True)

	return str(path)
