# Ankifier

Turns a list of French words into Anki cards with audio: Mistral writes the
example sentences, ElevenLabs reads them, AnkiConnect creates the notes.

Two ways in:

- **Generate** — type words, the model returns up to three senses each, with a
  sentence, a cloze deletion, a translation and a CEFR level.
- **Manual** — write both sides yourself. No AI call anywhere in this path.

## Architecture

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

## Setup

```bash
poetry install
cd web && pnpm install
```

Create a `.env` in the repo root:

```ini
AI_KEY=...                  # Mistral
ELEVEN_LABS_KEY=...         # ElevenLabs
```

Everything else has a default — see `src/ankifier/settings.py`. The ones worth
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
| `CORS_ORIGINS` | *(empty)* | comma-separated; empty means same-origin only |

Adding cards needs Anki running with the
[AnkiConnect](https://ankiweb.net/shared/info/2055492159) add-on.

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
preview is reused by the later add rather than generated twice.

## Tests

```bash
poetry run pytest
cd web && pnpm exec tsc -b && pnpm lint
```

The Python tests fake every connector, so nothing hits the network and no test
spends credits or touches your collection.
