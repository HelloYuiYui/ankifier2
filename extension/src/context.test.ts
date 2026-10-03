import { describe, expect, it } from 'vitest'

import { MAX_CONTEXT, cleanWord, sentenceAround } from './context'

const para =
	'Il fait très chaud. Il se regarde dans la glace avant de sortir. Puis il part.'

const around = (word: string, text = para) => {
	const start = text.indexOf(word)
	return sentenceAround(text, start, start + word.length, 'fr')
}

describe('sentenceAround', () => {
	it('picks the sentence the selection is in', () => {
		expect(around('glace')).toBe('Il se regarde dans la glace avant de sortir.')
	})

	it('handles a selection in the first and the last sentence', () => {
		expect(around('chaud')).toBe('Il fait très chaud.')
		expect(around('part')).toBe('Puis il part.')
	})

	it('returns every sentence a selection spans', () => {
		expect(around('chaud. Il se')).toBe(
			'Il fait très chaud. Il se regarde dans la glace avant de sortir.',
		)
	})

	it('returns the whole text when there is no sentence boundary', () => {
		expect(around('glace', 'la glace au citron')).toBe('la glace au citron')
	})

	it('does not break a sentence at a newline from the HTML source', () => {
		expect(around('glace', 'Il se regarde\n  dans la glace. Puis il part.')).toBe(
			'Il se regarde dans la glace.',
		)
	})

	it('collapses the whitespace a DOM text run carries', () => {
		expect(around('glace', 'Une\n\t  glace   fondue.')).toBe('Une glace fondue.')
	})

	it('windows an over-long block around the selection', () => {
		const filler = 'mot '.repeat(600)
		const text = `${filler}glace ${filler}`
		const out = around('glace', text)
		expect(out.length).toBeLessThanOrEqual(MAX_CONTEXT)
		expect(out).toContain('glace')
	})
})

describe('cleanWord', () => {
	it('trims the punctuation a double-click picks up', () => {
		expect(cleanWord(' glace, ')).toBe('glace')
		expect(cleanWord('«glace»')).toBe('glace')
	})

	it('keeps apostrophes and hyphens inside the word', () => {
		expect(cleanWord("l'eau.")).toBe("l'eau")
		expect(cleanWord('peut-être')).toBe('peut-être')
	})
})
