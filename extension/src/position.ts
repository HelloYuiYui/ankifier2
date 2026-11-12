import type { CSSProperties } from 'react'

import type { Rect } from './selection'

const PANEL_WIDTH = 380
/** Rough, only to decide between below and above the selection. */
const PANEL_HEIGHT = 380
const GAP = 6
const MARGIN = 8

function clampLeft(left: number, width: number): number {
	return Math.max(MARGIN, Math.min(left, window.innerWidth - width - MARGIN))
}

export function pillPosition(rect: Rect): CSSProperties {
	const below = rect.bottom + GAP + 32 < window.innerHeight
	return {
		left: clampLeft(rect.left, 120),
		...(below
			? { top: rect.bottom + GAP }
			: { bottom: window.innerHeight - rect.top + GAP }),
	}
}

export function panelPosition(rect: Rect): CSSProperties {
	const width = Math.min(PANEL_WIDTH, window.innerWidth - 2 * MARGIN)
	// Below when it fits, else whichever side has more room -- a selection at
	// the bottom of the screen opens the bubble upwards.
	const roomBelow = window.innerHeight - rect.bottom
	const below = roomBelow > PANEL_HEIGHT || roomBelow > rect.top
	return {
		width,
		left: clampLeft(rect.left, width),
		...(below
			? { top: rect.bottom + GAP, maxHeight: roomBelow - GAP - MARGIN }
			: {
					bottom: window.innerHeight - rect.top + GAP,
					maxHeight: rect.top - GAP - MARGIN,
				}),
	}
}
