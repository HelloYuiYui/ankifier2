import type { AddResult, CardDraft, GenerateRow } from '@ankifier/api'
import { describe, expect, it } from 'vitest'

import { type State, idle, reducer } from './bubbleState'
import type { Picked } from './selection'

const picked: Picked = {
	text: 'glace',
	context: 'Il se regarde dans la glace.',
	rect: { top: 0, bottom: 10, left: 0, right: 10 },
}
const row: GenerateRow = { sourceId: 's', text: 'glace', kind: 'generated' }
const draft = { id: 's#1', clozeSentence: '{{c1::glace}}' } as CardDraft
const result = { id: 's#1' } as AddResult
const retry = () => {}

const run = (state: State, ...actions: Parameters<typeof reducer>[1][]) =>
	actions.reduce(reducer, state)

describe('reducer', () => {
	it('walks a generated card from selection to done', () => {
		const state = run(
			idle,
			{ type: 'select', picked },
			{ type: 'load', picked, row },
			{ type: 'loaded', draft },
			{ type: 'edit', change: { translation: 'ice' } },
			{ type: 'add' },
			{ type: 'added', result },
		)
		expect(state).toEqual({
			step: 'done',
			picked,
			row,
			draft: { ...draft, translation: 'ice' },
			result,
		})
	})

	it('starts an as-is card from the selected text, editable before the request', () => {
		const state = run(
			idle,
			{ type: 'select', picked },
			{ type: 'startAsIs' },
			{ type: 'editAsIs', text: 'la [[glace]]' },
		)
		expect(state).toEqual({ step: 'asIs', picked, text: 'la [[glace]]' })
	})

	it('a selection that is cleared goes back to idle', () => {
		expect(run({ step: 'pill', picked }, { type: 'select', picked: null })).toBe(
			idle,
		)
	})

	it('ignores an edit while the card is being added', () => {
		const adding: State = { step: 'adding', picked, row, draft }
		expect(reducer(adding, { type: 'edit', change: { translation: 'x' } })).toBe(
			adding,
		)
	})

	it('ignores a reply for a step that is no longer showing', () => {
		const review: State = { step: 'review', picked, row, draft }
		expect(reducer(review, { type: 'loaded', draft })).toBe(review)
		expect(reducer(review, { type: 'added', result })).toBe(review)
	})

	it('a failure keeps the selection for a retry, but not after closing', () => {
		const loading: State = { step: 'loading', picked, row }
		expect(reducer(loading, { type: 'fail', message: 'down', retry })).toEqual({
			step: 'error',
			picked,
			message: 'down',
			retry,
		})
		expect(reducer(idle, { type: 'fail', message: 'down', retry })).toBe(idle)
	})
})
