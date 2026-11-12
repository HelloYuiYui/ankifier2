import type { AudioSide, ManualRowInput } from '../api/types'

/** Mirrors cloze.MARKER_RE: a front with a complete marker is a cloze card. */
const MARKER_RE = /\[\[.+?\]\]/

export const hasMarker = (text: string) => MARKER_RE.test(text)

/** Rows persisted before this column existed have no side; they read the front. */
export const sideOf = (row: ManualRowInput): AudioSide => row.audioSide ?? 'front'
