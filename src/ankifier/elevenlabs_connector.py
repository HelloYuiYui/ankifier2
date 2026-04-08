import os
import re

from elevenlabs import ElevenLabs


def init_client() -> ElevenLabs:
    """Create and return an ElevenLabs client using ELEVEN_LABS_KEY from environment."""
    api_key = os.environ.get("ELEVEN_LABS_KEY")
    if not api_key:
        raise ValueError("ELEVEN_LABS_KEY environment variable is not set")
    return ElevenLabs(api_key=api_key)


def sanitize_filename(text: str) -> str:
    """Sanitize a string for use as a filename."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s]+', '_', text)
    return text


def generate_audio(
    client: ElevenLabs,
    text: str,
    output_path: str,
    voice: str = "JBFqnCBsd6RMkjVDRZzb" #"TYKLc7ViOIGE13dSZYlK", # Rachel voice ID
) -> str:
    """
    Generate TTS audio for the given text and save to output_path.

    Returns the output path on success.
    """
    audio_iterator = client.text_to_speech.convert(
        text=text,
        voice_id=voice,
        model_id="eleven_multilingual_v2",
        output_format="mp3_44100_128",
    )

    with open(output_path, 'wb') as f:
        for chunk in audio_iterator:
            f.write(chunk)

    return output_path
