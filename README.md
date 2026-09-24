# Ankifier

Ankifier is an AI-assisted flashcard generator to help users speed up their flashcard generation process. Its main strength and function is to take in words in the target language the user may come across during their studies, generate sentences that use the given words, generate audio for the sentence provided or generated, and combine them all into a cloze card in Anki. Currently it only support French, as it is the language I focus on at the moment. In the foreseeable future I intend to expand it to include Bulgarian and German too. 

There are three ways of using Ankifier at the moment:

1. Target word or phrase in a sample AI-generated sentence in cloze format. 
2. Target word, phrase, or sentence with an AI generated sentence in basic format.
3. Manual entry of front and back values, in cloze or basic format. 

It uses Mistral as its text generator model, ElevenLabs for audio generation, and AnkiConnect to add cards to Anki. 

This tool is highly optimised for my own personal learning process that combines multiple methods, primarily comprehensible input with some targeted grammar practice. Everyone learns differently, so this may not work for you. Some tips to make the best out of it: 

*  This is an assistive tool, not a standalone resource. Engage with your target language, and note down the words you don't know and want to learn. 
*  Anki requires long-term determination and commitment to be regular with your learning. Showing up daily is crucial if you want to progress. 
* I found it a motivating factor for continuous study to add at least a few words every day rather adding many words in one day and studying them later. This ensures continuous exposure and input in the target language. 


## Setup 

As AnkiConnect runs locally, we need to run the server locally too in order to add cards to Anki. Once you clone this repository and ensure you have `poetry` and `pnpm`, run the following commands on the terminal to download needed dependencies. 

```bash
poetry install
pnpm install
```

You will need to fetch your own Mistral and ElevenLabs API keys. Once you get these, create a `.env` in the repo root:

```ini
AI_KEY=...                  # Mistral
ELEVEN_LABS_KEY=...         # ElevenLabs
```

Once this is set up and you have Anki running with [AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on, on the root directory, run the following command to start the server:

```bash
poetry run ankifier
```

<!-- Everything else has a default — see `src/ankifier/settings.py`. The ones worth
knowing:

| Variable | Default | |
|---|---|---|
| `ANKI_DECK` | `French::Vocabulary` | generated cards |
| `ANKI_ASIS_DECK` | `French::Grammar` | "as is" cards |
| `ANKI_MANUAL_DECK` | `French::Manual` | hand-written cards |
| `ANKI_TAGS` | `ankifier` | comma-separated |
| `TARGET_LANG` | `French` | |
| `AUDIO_DIR` | `audio` | generated mp3s |
| `ANKICONNECT_URL` | `http://localhost:8765` | |
| `CORS_ORIGINS` | *(empty)* | comma-separated; empty means same-origin only | -->


## Usage

When given a plain word in generate format, Mistral AI will generate a sentence that uses the given word and its translation, with the target word masked in cloze format. If `as-is` button is ticked, it will take the given text as is, pass it onto Mistral for translation and ElevenLabs for audio generation. 

To generate using your own custom sentence as a cloze card, put your target word or phrase in the sentence between ``[[...]]`` and Mistral will generate a translation for the sentence and you'll have a cloze card with the marked section masked. 

| You type | Anki gets |
|---|---|
| `Le [[chat]] dort` | `Le {{c1::chat}} dort` |
| `Il faut que tu [[sois:être]] là` | `Il faut que tu {{c1::sois::être}} là` |
| `[[a]] et [[b]]` | `{{c1::a}} et {{c2::b}}` |

Everything after the first colon is the hint Anki shows on the card; a hint is
never read aloud. 

<!-- The rendering lives in `cloze.py` alone and is reached over
`POST /api/cloze/preview`, so the preview you see while typing is produced by
exactly the code that builds the card. -->

## Technical Details

To Do 

<!-- ## Architecture

A Python API and a React SPA, and nothing else at runtime.

```
web/                    React + TypeScript + Vite    (pnpm)
src/ankifier/           FastAPI + the connectors     (poetry)
  api.py                routes
  services.py           generation + card creation
  schemas.py            the wire contract
  settings.py           every tunable
  cloze.py              [[marker]] -> {{c1::cloze}}
  mistral_connector.py  elevenlabs_connector.py  anki_connector.py
```

The server is **stateless**: it holds no batch between requests. The client
keeps its cards and posts back the ones you kept, which is why a reload restores
your review table instead of losing it.

In development Vite serves the SPA on `:5173` and proxies `/api` to the Python
server on `:8000`. In production `pnpm build` writes the SPA into
`src/ankifier/static/` and FastAPI serves both — one process, one port. The
client reads `VITE_API_BASE` (empty = same origin), so the two can be split onto
separate hosts later with no code change.

## Running

**Development** — two terminals:

```bash
poetry run ankifier          # API on http://127.0.0.1:8000
cd web && pnpm dev           # UI  on http://localhost:5173
```

Use the Vite URL. It proxies `/api` to the Python server, so there is no CORS to
configure.

**Single process:**

```bash
cd web && pnpm build         # writes into src/ankifier/static/
poetry run ankifier          # serves the API and the UI on :8000
```

## Marker syntax

Mark the part of a sentence to hide with double brackets:

| You type | Anki gets |
|---|---|
| `Le [[chat]] dort` | `Le {{c1::chat}} dort` |
| `Il faut que tu [[sois:être]] là` | `Il faut que tu {{c1::sois::être}} là` |
| `[[a]] et [[b]]` | `{{c1::a}} et {{c2::b}}` |

Everything after the first colon is the hint Anki shows on the card; a hint is
never read aloud. Hyphens are ordinary characters, so `est-ce` and `rendez-vous`
need no escaping.

The rendering lives in `cloze.py` alone and is reached over
`POST /api/cloze/preview`, so the preview you see while typing is produced by
exactly the code that builds the card.

## API

| | |
|---|---|
| `GET /api/health` | Anki reachable, keys present, decks, target language |
| `GET /api/decks` | every deck in the collection |
| `POST /api/generate` | words → card drafts (+ per-row errors) |
| `POST /api/cloze/preview` | batched marker rendering |
| `POST /api/cards/add` | audio + notes for the drafts you kept |
| `POST /api/audio/preview` | audio for one text |
| `GET /api/audio/{filename}` | serves a generated mp3 |

Interactive docs at http://127.0.0.1:8000/docs — that is also where you check
that `web/src/api/types.ts` still matches `schemas.py`.

### Dry run

`POST /api/cards/add` with `{"dryRun": true}` (the **Dry run** button in Review)
resolves the deck, filename and note type for every card and reports what it
would do — without writing to Anki, creating a deck, or spending any ElevenLabs
credits.

## Audio filenames

Audio is named by a hash of the spoken text, the voice and the model:
`ankifier_{readable}_{digest}.mp3`. The same text always maps to the same file
and different text never collides — so editing a sentence gives the card its own
audio instead of overwriting the audio of one already in your collection, and a
preview is reused by the later add rather than generated twice. -->

<!-- ## Tests

```bash
poetry run pytest
```

The Python tests fake every connector, so nothing hits the network and no test
spends credits or touches your collection.

## Checks

The front-end runs through pnpm from the repo root, the back-end through Poetry.
CI runs exactly these.

```bash
pnpm format:check            # prettier
pnpm lint                    # eslint
pnpm typecheck               # tsc -b --noEmit

poetry run ruff check .      # lint
poetry run ruff format .     # format
```

`pnpm format` and `pnpm lint:fix` write the fixes rather than reporting them.
Each root script is a thin `pnpm --filter web ...`, so `pnpm --filter web lint`
and `cd web && pnpm lint` do the same thing.

Prettier owns formatting and `eslint-config-prettier` switches off every rule
that would disagree with it, so the two never fight. ESLint is type-aware: it
reads the project's tsconfig, which is why `pnpm lint` is slower than a
syntax-only linter and catches things like an unawaited promise. -->
