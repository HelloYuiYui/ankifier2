"""Benchmark the local MLX server against real vocabulary.

Phase 1 exists to answer two questions before building anything on top of it:
is a 4-bit 7B good enough at the target language, and is it fast enough to
live with?  This prints both the timings and the generated sentences so you
can judge them yourself.

Start the server first (poetry run python -m llm_server.server), then:
    poetry run python -m llm_server.benchmark glace parler grand
    poetry run python -m llm_server.benchmark --file words.txt
"""
import argparse
import os
import sys
import time

from ankifier.csv_parser import parse_line
from ankifier.local_connector import init_client, query_senses


def run_word(client, word: str, target_lang: str) -> float | None:
    """Query one word, print its senses, and return the elapsed seconds."""
    entry = parse_line(word)
    started = time.monotonic()

    try:
        senses = query_senses(client, entry, target_lang)
    except Exception as e:
        print(f"\n{word}: FAILED after {time.monotonic() - started:.1f}s -- {e}")
        return None

    elapsed = time.monotonic() - started
    print(f"\n{word}  ({elapsed:.1f}s, {len(senses)} sense(s))")
    for sense in senses:
        level = sense.level.value if sense.level else "--"
        print(f"  {sense.sense_number}. [{level}] {sense.sense_description}")
        print(f"     {sense.sentence}")
        print(f"     -> {sense.translation}")
        print(f"     cloze: {sense.cloze_sentence}")

    return elapsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("words", nargs="*", help="Words to test")
    parser.add_argument("--file", help="Read words from a file, one per line")
    args = parser.parse_args(argv)

    words = list(args.words)
    if args.file:
        with open(args.file) as f:
            words.extend(line.strip() for line in f if line.strip())

    if not words:
        parser.error("give some words, or --file")

    target_lang = os.environ.get("TARGET_LANG", "French")
    client = init_client()
    print(f"Model: {client.model}")
    print(f"Server: {client.base_url}")
    print(f"Language: {target_lang}, {len(words)} word(s)")

    timings = [t for t in (run_word(client, w, target_lang) for w in words) if t is not None]

    if not timings:
        print("\nEvery word failed. Is the server running?")
        return 1

    print(f"\n{'-' * 50}")
    print(f"Succeeded:  {len(timings)}/{len(words)}")
    print(f"First call: {timings[0]:.1f}s (includes cold prompt prefill)")
    if len(timings) > 1:
        rest = timings[1:]
        print(f"Subsequent: {sum(rest) / len(rest):.1f}s avg, "
              f"{min(rest):.1f}s min, {max(rest):.1f}s max")
    print(f"Total:      {sum(timings):.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
