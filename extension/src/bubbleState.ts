import type { AddResult, CardDraft, GenerateRow } from '@ankifier/api'

import type { Picked } from './selection'

export type State =
	| { step: 'idle' }
	| { step: 'pill'; picked: Picked }
	/** As-is text shown for editing first: its [[markers]] must exist before
	 * the request, because Mistral writes their hints at generate time. */
	| { step: 'asIs'; picked: Picked; text: string }
	| { step: 'loading'; picked: Picked; row: GenerateRow }
	| { step: 'review'; picked: Picked; row: GenerateRow; draft: CardDraft }
	| { step: 'adding'; picked: Picked; row: GenerateRow; draft: CardDraft }
	| {
			step: 'done'
			picked: Picked
			row: GenerateRow
			draft: CardDraft
			result: AddResult
	  }
	| { step: 'error'; picked: Picked; message: string; retry: () => void }

export type Action =
	| { type: 'select'; picked: Picked | null }
	| { type: 'close' }
	| { type: 'startAsIs' }
	| { type: 'editAsIs'; text: string }
	| { type: 'load'; picked: Picked; row: GenerateRow }
	| { type: 'loaded'; draft: CardDraft }
	| { type: 'edit'; change: Partial<CardDraft> }
	| { type: 'add' }
	| { type: 'added'; result: AddResult }
	| { type: 'fail'; message: string; retry: () => void }

export const idle: State = { step: 'idle' }

/** Actions that do not apply to the current step leave it unchanged. */
export function reducer(state: State, action: Action): State {
	switch (action.type) {
		case 'select':
			return action.picked ? { step: 'pill', picked: action.picked } : idle
		case 'close':
			return idle
		case 'startAsIs':
			return state.step === 'pill'
				? { step: 'asIs', picked: state.picked, text: state.picked.text }
				: state
		case 'editAsIs':
			return state.step === 'asIs' ? { ...state, text: action.text } : state
		case 'load':
			return { step: 'loading', picked: action.picked, row: action.row }
		case 'loaded':
			return state.step === 'loading'
				? { ...state, step: 'review', draft: action.draft }
				: state
		case 'edit':
			return state.step === 'review'
				? { ...state, draft: { ...state.draft, ...action.change } }
				: state
		case 'add':
			return state.step === 'review' ? { ...state, step: 'adding' } : state
		case 'added':
			return state.step === 'adding'
				? { ...state, step: 'done', result: action.result }
				: state
		case 'fail':
			return state.step === 'idle'
				? state
				: {
						step: 'error',
						picked: state.picked,
						message: action.message,
						retry: action.retry,
					}
	}
}
