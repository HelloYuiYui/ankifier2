import type { CardDraft } from './types'

/**
 * A generated card whose front has no cloze. services.preflight refuses these,
 * because Anki would otherwise get a Basic note instead of a cloze.
 */
export const needsCloze = (draft: Pick<CardDraft, 'kind' | 'clozeSentence'>) =>
	draft.kind === 'generated' && !draft.clozeSentence.includes('{{c')
