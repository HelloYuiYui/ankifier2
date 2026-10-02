/**
 * The wire types live in @ankifier/api (packages/api/src/types.ts), shared with
 * the browser extension. Re-exported here so the web app's imports never had to
 * change; only the types below are the web UI's own.
 */

import type { AudioSide } from '@ankifier/api'

export type * from '@ankifier/api'

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
	/** Optional: rows persisted before this column existed have no value. */
	audioSide?: AudioSide
	/** Comma-separated; optional for the same reason as `audioSide`. */
	tags?: string
}
