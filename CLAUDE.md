# Ankifier — orientation for Claude

Personal tool: turns French words/sentences into Anki cards (plus manual-only
Bulgarian cards; see "Languages"). Mistral writes the
sentence + translation, ElevenLabs reads it aloud, AnkiConnect (localhost:8765)
adds the note. Single user, runs locally, Anki must be open.

Use this file to know *where to look*; the code and its docstrings are the source
of truth. If something here disagrees with the code, trust the code and fix this file.

## Layout

```
src/ankifier/           FastAPI backend (Poetry, Python >=3.11)
  api.py                routes only: schema in -> services call -> schema out
  services.py           all the logic: generate_batch, add_one/add_cards, preflight, audio
  schemas.py            the wire contract (pydantic, snake_case in / camelCase out)
  models.py             internal dataclasses (WordEntry, Sense) used by connectors
  settings.py           every tunable (env/.env); deck_for() / tags_for() live here
  cloze.py              [[marker]] -> {{c1::cloze}}; pure, no I/O
  csv_parser.py         parse_line: "la glace", "promener (verb)", as_is
  mistral_connector.py  prompts + query_senses / translate_as_is -> list[Sense]
  elevenlabs_connector.py  TTS + content-addressed audio_filename()
  anki_connector.py     thin AnkiConnect wrapper (_invoke)
  static/               Vite build output (gitignored, may not exist)
packages/api/           @ankifier/api: shared by web/ and extension/, consumed as TS source
  src/types.ts          HAND-MIRRORED copy of schemas.py
  src/client.ts         createClient({ base }): the only code that calls the API
web/                    React 19 + TS + Vite + zustand + react-router (pnpm)
  src/api/              re-exports @ankifier/api (+ web-only types); api = createClient({base: ''})
  src/store/batch.ts    client-side batch state, persisted to localStorage
  src/routes/           GenerateInput (/), ManualInput (/manual), Review, Results
  e2e/                  Playwright smoke tests; every /api call faked in the browser (fakeApi.ts)
extension/              Chrome MV3 extension, WXT + React (imports: false -> explicit imports)
  entrypoints/background.ts  the ONLY extension code that fetches (see "Extension" below)
  entrypoints/content/  shadow-root UI mounting src/Bubble.tsx on every page
  entrypoints/popup/    server URL + /api/health status
  src/messages.ts       typed content<->worker message contract; errors flattened to data
  src/selection.ts      Range -> {text, context sentence, rect}; string work in context.ts
tests/                  pytest; every connector is faked (no network, no credits)
```

## Core flow

1. **Generate** (`POST /api/generate`): rows of `kind` `generated` | `as_is` ->
   `services.generate_batch` -> Mistral -> `CardDraft`s + per-row `GenerateError`s.
   Serial, about 2s per row. One row can fan out into several senses, with ids `f"{source_id}#{n}"`.
   `max_senses` (1..3, default 3) caps that. `context` (the page sentence) makes a
   one-sense request pick the meaning used there. The extension sends `1` plus the context.
   Before generating, the web page asks `POST /api/words/existing` how many notes each word
   already has (`services.word_notes_query`) and shows it as a warning, never a block.
2. **Manual** cards never reach the API until add. The client builds drafts itself,
   using `POST /api/cloze/preview` (batched) for the marker rendering.
3. **Review** happens client-side (keep/discard, edit cells). It marks cards Anki already
   has via `POST /api/cards/check` (`services.duplicate_ids`, AnkiConnect `canAddNotes`).
4. **Add** (`POST /api/cards/add`): `preflight` (fails the whole batch with a 503 before
   any side effect) -> `duplicate_ids` -> `add_one` per card: TTS -> `storeMediaFile` -> `addNote`.
   A duplicate is skipped before TTS, so it costs no credits.
   The note type is Cloze if `"{{c"` is in `cloze_sentence`, otherwise Basic.
   `dryRun` skips TTS, deck creation and note writes.

## Invariants (don't break these)

- **Stateless server.** No session and no server-side batch. The client posts back the
  drafts it kept.
- **The client never picks a deck, tags or audio filename.** These are derived server-side
  from `kind` (+ `deck_target` for manual cards, + `language`) and the text. `deck_target` is an enum
  (`vocabulary` | `grammar`), never a deck name. The one exception is `extra_tags`: raw
  comma-separated text the user types, which `services.parse_tags` splits and *appends*.
  It can't remove a derived tag.
- **A `generated` card is always a cloze.** If Mistral's `hidden_text` isn't in its sentence,
  `query_senses` asks it once more to fix just those senses. If it still misses, the sentence is
  left unclozed, and `needsCloze` (`@ankifier/api`) and `services.preflight` block the add until
  the user marks it. It is never prepended and never falls back to a Basic note.
- **Duplicate checks build the note with `services.note_args`, the same as the add,** so they
  can't disagree with what `addNote` rejects. The per-word check finds notes by the stem of the
  `[sound:...]` filename (`elevenlabs_connector.audio_stem`): changing how stems are made
  (e.g. #14) hides every note made before from it.
- **Changing `schemas.py` means changing `packages/api/src/types.ts` in the same change.**
  No codegen. Check `/docs`.
- **Audio is content-addressed:** `{readable}_{hash}.mp3`, so identical text
  reuses the file. The `[sound:...]` tag always goes on the note's **back** field.
  `audio_side` only decides *what* is read (sentence vs translation).
- **Hints are never read aloud.** `cloze.render` returns `(plain, cloze)`, and only
  `plain` goes to TTS.
- Route handlers are plain `def` (the connectors block), not `async def`.
- The SPA catch-all route in `api.py` must stay registered **last**.
- CORS is off unless `CORS_ORIGINS` is set, because the server spends credits and writes to Anki.
  The extension does not need it (see below). Never open CORS for the extension.

## Extension

The flow is select -> pill (**Card** = `generated`, **As is**) -> one draft -> edit in
the bubble -> `/api/cards/add`. A content script's `fetch` runs with the page's origin,
so CORS and Private Network Access block it. That's why every call goes through
`browser.runtime.sendMessage` to the background worker, whose `host_permissions`
(127.0.0.1/localhost only) exempt it. The shadow root is `closed`, so pages can't
click "Add". Planned next: a sense picker, which is `POST /api/senses` plus a
`sense` field on `GenerateRow` plus a `choosing` bubble step.

## Cloze marker syntax

`Le [[chat]] dort` -> `Le {{c1::chat}} dort`; `[[sois:être]]` -> `{{c1::sois::être}}`
(inline hints are for manual cards only; as-is cards get hints from Mistral by position).
Every marker is `c1`, so a sentence with several is still one card.
Empty hint -> no `::`. Stray `[[`/`]]` are stripped. All of this lives in `cloze.py`.

## Languages

`CardDraft.language` (`french` | `bulgarian`, default `french`). Only French is generated:
the prompts, article parsing and gender enum are French, so a validator rejects any
other language unless `kind == "manual"`. `GenerateRow` has no language. The language
picks the deck and the voice (`settings.voice_for`: `ELEVENLABS_VOICE_ID_<LANG>`, empty =
the default voice). ElevenLabs takes the *language* from the text: `eleven_multilingual_v2`
ignores `language_code`. The voice is in the audio hash, so `/api/audio/preview` takes
`language` too. Web: the manual deck toggle's third option sends `language: 'bulgarian'`.
A new language means one enum value, a deck setting, and a voice setting.

## Decks (settings.deck_for)

`generated` -> `ANKI_DECK` (French::Vocabulary); `as_is` -> `ANKI_ASIS_DECK`
(French::Grammar); `manual` -> `ANKI_MANUAL_DECK` (French::Grammar), or vocab/grammar via
`deck_target`; any Bulgarian card -> `ANKI_BULGARIAN_DECK` (Bulgarian::Vocabulary). Tags (`services.note_tags`): `ANKI_TAGS` + `as-is`/`manual` + the CEFR level
+ `noun`/`verb`/`adjective`/`adverb` + `masculine`/`feminine` for nouns. A missing value is no
tag at all (no `unknown-*`): no level, a function word, a non-noun. A
`(verb)`-style annotation in the input overrides Mistral's part of speech; only a noun keeps a gender.
Then the user's `extra_tags` (spaces inside a tag become `-`, duplicates dropped).

## Commands

```bash
poetry run ankifier            # API on :8000 (also serves web build if present)
cd web && pnpm dev             # UI on :5173, proxies /api -> 127.0.0.1:8000
pnpm build:ext / pnpm dev:ext  # extension -> extension/.output/chrome-mv3 (load unpacked)
pnpm --filter extension test   # vitest (context.ts)
pnpm --filter web test         # vitest (lib/)
pnpm --filter web test:e2e     # Playwright, /api faked in the browser (web/e2e/fakeApi.ts)
poetry run pytest -q
poetry run ruff check . && poetry run ruff format --check .
pnpm format:check && pnpm lint && pnpm typecheck   # from repo root; pnpm -r over all 3 packages
pnpm build                     # writes SPA into src/ankifier/static/
```

CI (`.github/workflows/ci.yaml`) runs all of the above.

## Conventions

- **Tabs** everywhere (Python via `ruff format` indent-style=tab, Prettier for web),
  except YAML. Line length 88. One `.prettierrc.json` at the root, but a `.prettierignore`
  per package (Prettier reads that one only from the cwd).
- Comments are sparse and explain *why* when the code can't: a constraint, a non-obvious
  choice. No history or changelog ("used to", "since X"), and no docstrings that
  restate a self-explanatory function.
- `get_settings()` is `lru_cache`d. Tests clear it via the autouse fixture in
  `tests/conftest.py`. Add any new env var to `_ANKIFIER_ENV` there.
- Mistral prompt strings: their whitespace is sent to the model, so don't rewrap them.
- `.env` holds real keys (`AI_KEY`, `ELEVEN_LABS_KEY`). Never read or print it.
- `requirements.md` is the original spec and is partly outdated (it mentions `-...-`
  markers and utils/). The README's commented-out sections are closer to current.
