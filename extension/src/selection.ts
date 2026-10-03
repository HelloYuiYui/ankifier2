/**
 * The DOM half of reading a selection: which text, where on screen, and the
 * sentence it came from. The string work is in context.ts.
 *
 * Captured at mouseup, before anything else happens: the Range is gone the
 * moment the user clicks the pill, which moves focus into the shadow root.
 */

import { collapse, sentenceAround } from './context'

/** Longer than this is not a word or a sentence someone means to learn. */
const MAX_SELECTION = 400

// The nearest of these around the selection is taken as its paragraph. Checked
// in two passes so that a <p> inside a layout <div> wins over the <div>.
const BLOCKS = 'p, li, td, th, dd, dt, blockquote, figcaption, h1, h2, h3, h4, h5, h6'
const FALLBACK_BLOCKS = 'article, section, div'

export interface Rect {
	top: number
	bottom: number
	left: number
	right: number
}

export interface Picked {
	/** The selection with its whitespace collapsed. */
	text: string
	/** The sentence(s) around it, for GenerateRow.context. May be ''. */
	context: string
	/** Viewport coordinates, for positioning the pill and the bubble. */
	rect: Rect
}

export function readSelection(): Picked | null {
	const sel = window.getSelection()
	if (!sel || sel.isCollapsed || sel.rangeCount === 0) return null

	const text = collapse(sel.toString())
	if (!text || text.length > MAX_SELECTION) return null

	const range = sel.getRangeAt(0)
	const start = elementOf(range.startContainer)
	if (!start || isEditable(start)) return null

	const box = range.getBoundingClientRect()
	// A selection with no layout box (hidden text, an SVG oddity) has nowhere
	// to put the pill.
	if (!box.width && !box.height) return null

	return {
		text,
		context: contextOf(range, start),
		rect: { top: box.top, bottom: box.bottom, left: box.left, right: box.right },
	}
}

function contextOf(range: Range, start: Element): string {
	const block = start.closest(BLOCKS) ?? start.closest(FALLBACK_BLOCKS)
	if (!block) return ''

	// Offsets measured with Range.toString() on both sides, so the block text
	// and the selection agree on what counts as text.
	const before = document.createRange()
	before.setStart(block, 0)
	before.setEnd(range.startContainer, range.startOffset)
	const from = before.toString().length
	const to = from + range.toString().length

	const whole = document.createRange()
	whole.selectNodeContents(block)

	return sentenceAround(
		whole.toString(),
		from,
		to,
		document.documentElement.lang || undefined,
	)
}

function elementOf(node: Node): Element | null {
	return node instanceof Element ? node : node.parentElement
}

/** Selecting in a text box is editing, not reading. */
function isEditable(el: Element): boolean {
	return (
		el.closest(
			'input, textarea, [contenteditable]:not([contenteditable="false"])',
		) !== null
	)
}
