/**
 * The batch, held client-side.
 *
 * This is what replaced web.py's module-level `_store`, and it is strictly
 * better in three ways: rows are keyed by id rather than by list position, the
 * drafts survive the add step instead of being overwritten by the summary, and
 * persisting to localStorage means a reload restores the table rather than
 * losing it.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import type {
	AddResult,
	AudioSide,
	CardDraft,
	ManualDeck,
	GenerateError,
	GenerateRowInput,
	ManualRowInput,
} from '../api/types'

export type Phase = 'input' | 'working' | 'review' | 'adding' | 'done'

export const newId = () =>
	// crypto.randomUUID needs a secure context; localhost qualifies, but a plain
	// http:// origin on another host does not.
	globalThis.crypto?.randomUUID?.() ?? `id-${Math.random().toString(36).slice(2)}`

export const emptyGenerateRow = (): GenerateRowInput => ({
	id: newId(),
	text: '',
	asIs: false,
})

export const emptyManualRow = (audioSide: AudioSide = 'back'): ManualRowInput => ({
	id: newId(),
	front: '',
	back: '',
	audioSide,
})

interface BatchState {
	phase: Phase
	/** Which input table the current batch came from. */
	source: 'generate' | 'manual'

	generateRows: GenerateRowInput[]
	manualRows: ManualRowInput[]
	/** The deck the manual table adds to. Persisted, so it sticks between visits. */
	manualDeck: ManualDeck
	/** The side the last "all rows" pick chose; new manual rows start with it. */
	manualAudioSide: AudioSide

	drafts: CardDraft[]
	/** Keyed by draft id, never by index -- that was the old bug. */
	keep: Record<string, boolean>
	errors: GenerateError[]
	results: AddResult[] | null
	/** A batch-wide failure (Anki down, key missing), not a per-card one. */
	failure: string | null

	setGenerateRows: (rows: GenerateRowInput[]) => void
	setManualRows: (rows: ManualRowInput[]) => void
	setManualDeck: (deck: ManualDeck) => void
	/** Sets every manual row's side at once; a row can still be changed after. */
	setManualAudioSide: (side: AudioSide) => void

	startWorking: (source: 'generate' | 'manual') => void
	setDrafts: (drafts: CardDraft[], errors?: GenerateError[]) => void
	updateDraft: (id: string, patch: Partial<CardDraft>) => void
	toggleKeep: (id: string, value?: boolean) => void
	setAllKeep: (value: boolean) => void

	startAdding: () => void
	setResults: (results: AddResult[]) => void
	fail: (message: string) => void

	reset: () => void
	resetAll: () => void
}

const initial = {
	phase: 'input' as Phase,
	source: 'generate' as const,
	generateRows: [emptyGenerateRow()],
	manualRows: [emptyManualRow()],
	manualDeck: 'vocabulary' as ManualDeck,
	manualAudioSide: 'back' as AudioSide,
	drafts: [],
	keep: {},
	errors: [],
	results: null,
	failure: null,
}

export const useBatch = create<BatchState>()(
	persist(
		(set) => ({
			...initial,

			setGenerateRows: (generateRows) => set({ generateRows }),
			setManualRows: (manualRows) => set({ manualRows }),
			setManualDeck: (manualDeck) => set({ manualDeck }),
			setManualAudioSide: (audioSide) =>
				set((s) => ({
					manualAudioSide: audioSide,
					manualRows: s.manualRows.map((r) => ({ ...r, audioSide })),
				})),

			startWorking: (source) =>
				set({
					phase: 'working',
					source,
					failure: null,
					results: null,
					errors: [],
				}),

			setDrafts: (drafts, errors = []) =>
				set({
					drafts,
					errors,
					// Everything is kept by default; review is for unticking.
					keep: Object.fromEntries(drafts.map((d) => [d.id, true])),
					phase: 'review',
					failure: null,
				}),

			updateDraft: (id, patch) =>
				set((s) => ({
					drafts: s.drafts.map((d) => (d.id === id ? { ...d, ...patch } : d)),
				})),

			toggleKeep: (id, value) =>
				set((s) => ({ keep: { ...s.keep, [id]: value ?? !s.keep[id] } })),

			setAllKeep: (value) =>
				set((s) => ({
					keep: Object.fromEntries(s.drafts.map((d) => [d.id, value])),
				})),

			startAdding: () => set({ phase: 'adding', failure: null }),

			// Drafts are deliberately kept here: that is what makes "retry the
			// failures" a re-POST of a subset rather than a re-run of the batch.
			setResults: (results) => set({ results, phase: 'done' }),

			fail: (failure) =>
				set((s) => ({
					failure,
					phase: s.drafts.length ? 'review' : 'input',
				})),

			reset: () =>
				set({
					phase: 'input',
					drafts: [],
					keep: {},
					errors: [],
					results: null,
					failure: null,
				}),

			resetAll: () =>
				set({
					...initial,
					generateRows: [emptyGenerateRow()],
					manualRows: [emptyManualRow()],
				}),
		}),
		{
			name: 'ankifier-batch',
			// Not persisted: `phase` would restore mid-flight states like 'adding',
			// and a transient failure message should not outlive the page.
			partialize: ({ phase: _phase, failure: _failure, ...rest }) => rest,
		},
	),
)

export const keptDrafts = (s: { drafts: CardDraft[]; keep: Record<string, boolean> }) =>
	s.drafts.filter((d) => s.keep[d.id])
