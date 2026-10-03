/**
 * What to send for a selection: the text itself, and the sentence around it.
 *
 * Pure string work, no DOM, so it can be tested without a browser. The content
 * script does the one DOM-bound step -- turning a Range into a block of text and
 * offsets inside it -- and hands the result here.
 */

/** GenerateRow.context is capped at this on the server; a longer one is a 422. */
export const MAX_CONTEXT = 1000

/**
 * The sentence(s) of `text` that the selection [start, end) falls in.
 *
 * A selection spanning a sentence boundary gets every sentence it touches. A
 * block with no usable boundary (a table cell, a run-on caption) is windowed
 * around the selection rather than sent whole or cut off before it.
 */
export function sentenceAround(
	text: string,
	start: number,
	end: number,
	locale?: string,
): string {
	// One space per whitespace character: DOM text keeps the newlines of the
	// HTML source, and ICU reads a newline as a sentence break. Same length,
	// so start and end still point at the selection.
	text = text.replace(/\s/g, ' ')
	const segmenter = new Intl.Segmenter(locale, { granularity: 'sentence' })
	let from = -1
	let to = -1
	for (const { index, segment } of segmenter.segment(text)) {
		const segEnd = index + segment.length
		// Overlaps the selection. The `index === start` case catches an empty
		// selection sitting exactly on a boundary.
		if (index < end && segEnd > start) {
			if (from === -1) from = index
			to = segEnd
		} else if (index === start && from === -1) {
			from = index
			to = segEnd
		}
	}
	if (from === -1) return ''

	const sentence = collapse(text.slice(from, to))
	if (sentence.length <= MAX_CONTEXT) return sentence

	// Too long to be a sentence. Centre a window on the selection instead.
	const mid = Math.floor((start + end) / 2)
	const half = Math.floor(MAX_CONTEXT / 2)
	const lo = Math.max(from, mid - half)
	return collapse(text.slice(lo, lo + MAX_CONTEXT)).slice(0, MAX_CONTEXT)
}

/**
 * The selection as a word to look up: whitespace collapsed and the punctuation
 * a double-click drags along ("glace," or "«glace») trimmed off. Apostrophes
 * and hyphens inside the word ("l'eau", "peut-être") stay.
 */
export function cleanWord(selection: string): string {
	return collapse(selection).replace(/^[\p{P}\p{S}\s]+|[\p{P}\p{S}\s]+$/gu, '')
}

/** Whitespace collapsed, for text that becomes a card as it stands. */
export function collapse(text: string): string {
	return text.replace(/\s+/g, ' ').trim()
}
