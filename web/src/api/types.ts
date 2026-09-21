/**
 * Mirrors src/ankifier/schemas.py by hand.
 *
 * Hand-written rather than generated: it is ~100 lines against a codegen step
 * that needs a running server and has to be re-run from memory. When schemas.py
 * changes, change this with it -- http://127.0.0.1:8000/docs is where you check
 * the two still agree.
 */

export type Kind = 'generated' | 'as_is' | 'manual'
export type State = 'ok' | 'skipped' | 'error'
export type CEFRLevel = 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2'

/**
 * One prospective Anki note.
 *
 * The client holds these between generating and adding -- the server keeps no
 * batch state -- so this is both what /api/generate returns and what
 * /api/cards/add accepts.
 *
 * Deck, tags and audio filename are deliberately absent: the server derives
 * them from `kind` and from the text.
 */
export interface CardDraft {
  /** `${sourceId}#${n}`. Stable across regenerating a single input row. */
  id: string
  /** One per input line. Not unique -- a line can fan out into several cards. */
  sourceId: string
  kind: Kind

  /** The input line (or manual front). Display only. */
  word: string
  /** Display ordinal within a source line. Carries no identity. */
  senseNumber: number
  senseDescription: string

  /** What ElevenLabs reads. Always marker-free. Editable at review. */
  sentence: string
  /** The Anki "Text" (Cloze) or "Front" (Basic) field. Editable at review. */
  clozeSentence: string
  /** The Anki "Back Extra" / "Back" field. Editable at review. */
  translation: string

  /** Generation-time artefacts: shown, never edited -- they go stale. */
  hiddenText: string
  hint: string
  level: CEFRLevel | null

  /** Names the audio file when the spoken text is unwieldy. Cosmetic. */
  audioStem: string | null
}

export interface Status {
  state: State
  detail: string | null
}

export interface AddResult {
  id: string
  audio: Status
  card: Status
  deck: string
  /** Pre-encoded by the server. Treat as opaque -- never rebuild it. */
  audioUrl: string | null
}

// --- /api/generate ---------------------------------------------------------
export interface GenerateRow {
  sourceId: string
  text: string
  kind: 'generated' | 'as_is'
}

export interface GenerateError {
  sourceId: string
  text: string
  message: string
}

export interface GenerateResponse {
  cards: CardDraft[]
  errors: GenerateError[]
}

// --- /api/cloze/preview ----------------------------------------------------
export interface ClozeText {
  id: string
  text: string
  /** Manual cards carry `[[word:hint]]`; as-is cards get hints from Mistral. */
  inlineHints?: boolean
}

export interface ClozeResult {
  id: string
  plain: string
  cloze: string
}

export interface ClozePreviewResponse {
  results: ClozeResult[]
}

// --- /api/cards/add --------------------------------------------------------
export interface AddRequest {
  cards: CardDraft[]
  /** Everything except storeMediaFile and addNote. Costs nothing, writes nothing. */
  dryRun?: boolean
}

export interface AddResponse {
  results: AddResult[]
}

// --- /api/audio ------------------------------------------------------------
export interface AudioPreviewResponse {
  audioUrl: string
}

// --- /api/health -----------------------------------------------------------
export interface HealthResponse {
  anki: { ok: boolean; version: number | null; error: string | null }
  keys: { mistral: boolean; elevenlabs: boolean }
  decks: { generated: string; asIs: string; manual: string }
  targetLang: string
  /** null when Anki is down -- distinct from an empty collection. */
  ankiDecks: string[] | null
}

// --- client-side only ------------------------------------------------------
/** A row in the generate input table, before it reaches the server. */
export interface GenerateRowInput {
  id: string
  text: string
  asIs: boolean
}

/** A row in the manual input table. */
export interface ManualRowInput {
  id: string
  front: string
  back: string
  cloze: boolean
}
