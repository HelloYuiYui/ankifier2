import { type Dispatch, useEffect } from 'react'

import type { Action, State } from './bubbleState'
import { readSelection } from './selection'

/**
 * Shows the pill for the page's selection and hides it again. Events from
 * inside the (closed) shadow root reach the document retargeted to `host`,
 * which is how clicks on the pill or the bubble are told apart from the page.
 */
export function useSelectionPill(
	host: HTMLElement,
	step: State['step'],
	dispatch: Dispatch<Action>,
) {
	useEffect(() => {
		const fromUs = (e: Event) => e.composedPath().includes(host)
		// Only the pill follows the selection. An open bubble holds a card the
		// user may be editing, so selecting elsewhere must not throw it away.
		const passive = step === 'idle' || step === 'pill'
		const hidePill = () => {
			if (step === 'pill') dispatch({ type: 'close' })
		}

		const onUp = (e: Event) => {
			if (!passive || fromUs(e)) return
			// After this event's default action, or a click that clears the
			// selection still reads the old one.
			setTimeout(() => dispatch({ type: 'select', picked: readSelection() }))
		}
		const onDown = (e: Event) => {
			if (!fromUs(e)) hidePill()
		}
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape') hidePill()
		}

		document.addEventListener('mouseup', onUp)
		document.addEventListener('keyup', onUp)
		document.addEventListener('mousedown', onDown)
		document.addEventListener('keydown', onKey)
		// The pill is position: fixed, so on scroll it would float away from the
		// text it belongs to. The bubble stays: it is a panel, not a label.
		window.addEventListener('scroll', hidePill, { passive: true, capture: true })
		return () => {
			document.removeEventListener('mouseup', onUp)
			document.removeEventListener('keyup', onUp)
			document.removeEventListener('mousedown', onDown)
			document.removeEventListener('keydown', onKey)
			window.removeEventListener('scroll', hidePill, { capture: true })
		}
	}, [host, step, dispatch])
}
