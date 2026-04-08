import os

from ankifier.models import CardData, Sense, WordEntry, WordResult
from ankifier import mistral_connector, elevenlabs_connector, anki_connector


def get_sentences(entry: WordEntry, ai_client, target_lang: str) -> WordResult:
    """Get example sentences and senses for a word via AI client."""
    senses = mistral_connector.query_senses(ai_client, entry, target_lang)
    return WordResult(entry=entry, senses=senses)


def get_audio(
    word_result: WordResult,
    elevenlabs_client,
    audio_dir: str,
) -> list[tuple[Sense, str]]:
    """Generate audio for each sense's sentence. Returns list of (Sense, audio_path)."""
    results = []
    word_safe = elevenlabs_connector.sanitize_filename(word_result.entry.word)

    for sense in word_result.senses:
        filename = f"{word_safe}_{sense.sense_number}.mp3"
        output_path = os.path.join(audio_dir, filename)

        try:
            elevenlabs_connector.generate_audio(
                elevenlabs_client,
                sense.sentence,
                output_path,
            )
            results.append((sense, output_path))
            print(f"  Audio generated: {filename}")
        except Exception as e:
            print(f"  Warning: Audio generation failed for sense {sense.sense_number}: {e}")

    return results


def create_cards(
    word_result: WordResult,
    audio_paths: list[tuple[Sense, str]],
    deck_name: str,
    tags: list[str],
) -> list[int]:
    """Create Anki cards for each sense with audio. Returns list of note IDs."""
    note_ids = []

    for sense, audio_path in audio_paths:
        audio_filename = os.path.basename(audio_path)

        try:
            anki_connector.store_media_file(audio_filename, audio_path)

            note_id = anki_connector.add_cloze_note(
                deck_name=deck_name,
                cloze_text=sense.cloze_sentence,
                back_extra=sense.translation,
                audio_filename=audio_filename,
                tags=tags,
            )
            note_ids.append(note_id)
            print(f"  Card created: {sense.hint} (note ID: TEST)")
        except RuntimeError as e:
            if "duplicate" in str(e).lower():
                print(f"  Skipped (duplicate): {sense.hint}")
            else:
                print(f"  Warning: Failed to create card for sense {sense.sense_number}: {e}")

    return note_ids


def process_word(
    entry: WordEntry,
    client,
    elevenlabs_client,
    config: dict,
) -> list[int]:
    """Full pipeline for a single word: sentences -> audio -> cards.

    Catches exceptions so one word failure doesn't halt the batch.
    """
    print(f"\nProcessing: {entry.raw}")

    try:
        word_result = get_sentences(entry, client, config["target_lang"])
        print(f"  Found {len(word_result.senses)} sense(s)")

        for sense in word_result.senses:
            print(f"    {sense.sense_number}. {sense.hint}: {sense.sentence}")
    except Exception as e:
        print(f"  Error getting sentences: {e}")
        return []

    # try:
    #     audio_paths = get_audio(word_result, elevenlabs_client, config["audio_dir"])
    # except Exception as e:
    #     print(f"  Error generating audio: {e}")
    #     return []

    try:
        note_ids = create_cards(
            word_result,
            # audio_paths,
            config["deck_name"],
            config.get("tags", ["ankifier"]),
        )
        return note_ids
    except Exception as e:
        print(f"  Error creating cards: {e}")
        return []
