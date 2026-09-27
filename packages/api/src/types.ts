/**
 * Mirrors src/ankifier/schemas.py by hand.
 *
 * Hand-written rather than generated: it is ~100 lines against a codegen step
 * that needs a running server and has to be re-run from memory. When schemas.py
 * changes, change this with it -- http://127.0.0.1:8000/docs is where you check
 * the two still agree.
 *
 * Shared by web/ and extension/, so there is one mirror to keep in step rather
 * than two. Types that only the web UI uses live in web/src/api/types.ts.
 */

export type Kind = 'generated' | 'as_is' | 'manual'
export type State = 'ok' | 'skipped' | 'error'
export type CEFRLevel = 'A1' | 'A2' | 'B1' | 'B2' | 'C1' | 'C2'
/**
 * Which text ElevenLabs reads. It does not move the sound tag -- that is on the
 * note's back field either way, so audio only plays once the card is turned.
 */
export type AudioSide = 'front' | 'back'

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

	/** What ElevenLabs reads unless `audioSide` is 'back'. Marker-free. Editable. */
	sentence: string
	/** The Anki "Text" (Cloze) or "Front" (Basic) field. Editable at review. */
	clozeSentence: string
	/** The Anki "Back Extra" / "Back" field. Editable at review. */
	translation: string

	/** Generation-time artefacts: shown, never edited -- they go stale. */
	hiddenText: string
	hint: string
	level: CEFRLevel | null

	/** Read the front (`sentence`) or the back (`translation`) aloud. */
	audioSide: AudioSide
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
	/** 1..3, default 3. The extension asks for 1 -- one card, and faster. */
	maxSenses?: number
	/**
	 * The page sentence a word was selected from, so the model picks the sense
	 * meant there. At most 1000 characters. Ignored for `as_is`.
	 */
	context?: string | null
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
