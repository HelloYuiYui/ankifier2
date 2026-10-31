/**
 * The wire types live in @ankifier/api (packages/api/src/types.ts), shared with
 * the browser extension. Re-exported here so the web app's imports never had to
 * change; only the types below are the web UI's own.
 */

import type { AudioSide, DeckTarget } from '@ankifier/api'

export type * from '@ankifier/api'

// --- client-side only ------------------------------------------------------
/** A row in the generate input table, before it reaches the server. */
export interface GenerateRowInput {
	id: string
	text: string
	asIs: boolean
}

/**
 * The manual table's deck toggle. One choice in the UI, but two fields on the
 * wire: a Bulgarian card has a single deck, so it sends a language and no target.
 */
export type ManualDeck = DeckTarget | 'bulgarian'

/** A row in the manual input table. */
export interface ManualRowInput {
	id: string
	front: string
	back: string
	/** Optional: rows persisted before this column existed have no value. */
	audioSide?: AudioSide
}
