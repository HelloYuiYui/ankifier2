import argparse
import os
import sys

from dotenv import load_dotenv

from ankifier.csv_parser import read_csv
from ankifier.mistral_connector import init_client as init_mistral
from ankifier.claude_connector import init_client as init_claude
from ankifier.elevenlabs_connector import init_client as init_elevenlabs
from ankifier.anki_connector import check_connection, ensure_deck
from ankifier.utils.utils import process_word


def load_config() -> dict:
    """Load and validate configuration from environment variables."""
    load_dotenv()

    ai_key = os.environ.get("AI_KEY")
    if not ai_key:
        print("Error: AI_KEY environment variable is not set.")
        sys.exit(1)

    eleven_labs_key = os.environ.get("ELEVEN_LABS_KEY")
    if not eleven_labs_key:
        print("Error: ELEVEN_LABS_KEY environment variable is not set.")
        sys.exit(1)

    return {
        "ai_key": ai_key,
        "eleven_labs_key": eleven_labs_key,
        "deck_name": os.environ.get("ANKI_DECK", "French::Vocabulary"),
        "target_lang": os.environ.get("TARGET_LANG", "French"),
        "audio_dir": os.environ.get("AUDIO_DIR", "audio"),
        "tags": os.environ.get("ANKI_TAGS", "ankifier").split(","),
    }


def main(csv_path: str) -> None:
    """Run the full Ankifier pipeline."""
    config = load_config()

    print(f"Target language: {config['target_lang']}")
    print(f"Anki deck: {config['deck_name']}")
    print(f"Audio directory: {config['audio_dir']}")

    # Initialize clients
    print("\nInitializing AI clients...")
    ai_client = init_mistral()
    elevenlabs_client = init_elevenlabs()

    # Check AnkiConnect
    print("Checking AnkiConnect...")
    if not check_connection():
        print("Error: Cannot connect to AnkiConnect.")
        print("Please make sure Anki is open and AnkiConnect add-on is installed.")
        sys.exit(1)
    print("AnkiConnect is running.")

    # Ensure deck exists
    ensure_deck(config["deck_name"])

    # Create audio directory
    os.makedirs(config["audio_dir"], exist_ok=True)

    # Parse CSV
    print(f"\nReading words from: {csv_path}")
    entries = read_csv(csv_path)
    print(f"Found {len(entries)} word(s) to process.")

    # Process each word
    total_cards = 0
    errors = 0

    for entry in entries:
        note_ids = process_word(entry, ai_client, elevenlabs_client, config)
        if note_ids:
            total_cards += len(note_ids)
        else:
            errors += 1

    # Summary
    print(f"\n{'=' * 40}")
    print(f"Done! Processed {len(entries)} word(s).")
    print(f"Cards created: {total_cards}")
    if errors:
        print(f"Words with errors: {errors}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ankifier - Generate Anki cloze cards from vocabulary words")
    parser.add_argument("csv_path", help="Path to the CSV file containing target words")
    args = parser.parse_args()

    main(args.csv_path)
