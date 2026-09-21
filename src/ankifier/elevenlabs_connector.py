import hashlib
import re
from pathlib import Path

from elevenlabs import ElevenLabs

from ankifier.settings import get_settings


def init_client() -> ElevenLabs:
    """Create and return an ElevenLabs client using ELEVEN_LABS_KEY."""
    settings = get_settings()
    if not settings.eleven_labs_key:
        raise ValueError("ELEVEN_LABS_KEY environment variable is not set")
    return ElevenLabs(
        api_key=settings.eleven_labs_key, timeout=settings.elevenlabs_timeout
    )


def sanitize_filename(text: str) -> str:
    """Sanitize a string for use as a filename."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s]+', '_', text)
    return text


def audio_filename(text: str, stem: str | None = None) -> str:
    """Content-addressed filename for the audio of `text`.

    The name has to be derived from the spoken text, not from the word or the
    sense number. Those do not change when a sentence is edited, so a name built
    from them collides with the file of a card already in the collection -- and
    store_media_file would then silently replace that card's audio. Hashing the
    text (with the voice and model, since either changes the audio) means the
    same text always maps to the same file and different text never collides.

    The readable prefix is for finding and purging Ankifier's media in Anki; it
    carries no identity.
    """
    settings = get_settings()
    digest = hashlib.sha1(
        f"{settings.elevenlabs_voice_id}|{settings.elevenlabs_model}|{text}".encode()
    ).hexdigest()[:10]
    # sanitize_filename returns "" for all-punctuation input, which would leave
    # a name starting with an underscore.
    safe = sanitize_filename(stem or text)[:40] or "card"
    return f"ankifier_{safe}_{digest}.mp3"


def generate_audio(
    client: ElevenLabs,
    text: str,
    output_path: str | Path,
    *,
    skip_if_present: bool = True,
) -> str:
    """Generate TTS audio for `text` and save it to output_path.

    Because the path is content-addressed, a file that is already there holds
    exactly the audio this call would produce, so the default is to keep it and
    spend no credits. That is what makes previewing a row at review time free in
    aggregate: the later add finds the preview's file and reuses it.

    The download goes to a .part file and is renamed once complete, so an
    interrupted run can never leave a truncated mp3 that a later call would
    mistake for a finished one.
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
        with open(partial, 'wb') as f:
            for chunk in audio_iterator:
                f.write(chunk)
        partial.replace(path)
    finally:
        partial.unlink(missing_ok=True)

    return str(path)
