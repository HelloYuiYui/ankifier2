/**
 * The whole on-page UI: the pill beside a selection, then the bubble that
 * generates, reviews and adds one card.
 *
 * Nothing persists. The server keeps no batch and neither does this -- closing
 * the bubble discards the card, exactly as unticking a row does in web/.
 *
 * (Planned: a `choosing` step between the pill and `loading`, where the user
 * picks one of the word's senses before any sentence is written.)
 */

import type { AddResult, CardDraft, GenerateRow } from '@ankifier/api'
import { type CSSProperties, useEffect, useRef, useState } from 'react'

import { CardEditor } from './CardEditor'
import { cleanWord } from './context'
import { type Reply, send } from './messages'
import { type Picked, type Rect, readSelection } from './selection'

type Kind = GenerateRow['kind']

type State =
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

const PANEL_WIDTH = 380
/** Rough, only to decide between below and above the selection. */
const PANEL_HEIGHT = 380
/** How long a successful add stays on screen before the bubble closes. */
const DONE_MS = 2500

export function Bubble({ host }: { host: HTMLElement }) {
	const [state, setState] = useState<State>({ step: 'idle' })
	// Bumped by every request and by closing, so a reply that lands after the
	// user has moved on is dropped instead of reopening an old card.
	const run = useRef(0)

	const close = () => {
		run.current++
		setState({ step: 'idle' })
	}

	// Page listeners. Events from inside the (closed) shadow root reach the
	// document retargeted to `host`, which is how clicks on the pill or the
	// bubble are told apart from clicks on the page.
	const step = state.step
	useEffect(() => {
		const fromUs = (e: Event) => e.composedPath().includes(host)
		// Only the pill follows the selection. An open bubble holds a card the
		// user may be editing, so selecting elsewhere must not throw it away.
		const passive = step === 'idle' || step === 'pill'

		const onUp = (e: Event) => {
			if (!passive || fromUs(e)) return
			// After this event's default action, or a click that clears the
			// selection still reads the old one.
			setTimeout(() => {
				const picked = readSelection()
				setState(picked ? { step: 'pill', picked } : { step: 'idle' })
			})
		}
		const onDown = (e: Event) => {
			if (step === 'pill' && !fromUs(e)) setState({ step: 'idle' })
		}
		// The pill is position: fixed, so on scroll it would float away from
		// the text it belongs to. The bubble stays: it is a panel, not a label.
		const onScroll = () => {
			if (step === 'pill') setState({ step: 'idle' })
		}
		const onKey = (e: KeyboardEvent) => {
			if (e.key === 'Escape' && step === 'pill') setState({ step: 'idle' })
		}

		document.addEventListener('mouseup', onUp)
		document.addEventListener('keyup', onUp)
		document.addEventListener('mousedown', onDown)
		document.addEventListener('keydown', onKey)
		window.addEventListener('scroll', onScroll, { passive: true, capture: true })
		return () => {
			document.removeEventListener('mouseup', onUp)
			document.removeEventListener('keyup', onUp)
			document.removeEventListener('mousedown', onDown)
			document.removeEventListener('keydown', onKey)
			window.removeEventListener('scroll', onScroll, { capture: true })
		}
	}, [host, step])

	useEffect(() => {
		if (state.step !== 'done' || state.result.card.state !== 'ok') return
		const t = setTimeout(() => {
			run.current++
			setState({ step: 'idle' })
		}, DONE_MS)
		return () => clearTimeout(t)
	}, [state])

	const generate = async (picked: Picked, row: GenerateRow) => {
		const mine = ++run.current
		setState({ step: 'loading', picked, row })
		const reply = await send({ type: 'generate', row })
		if (mine !== run.current) return

		const retry = () => void generate(picked, row)
		if (!reply.ok) return setState(failed(picked, reply, retry))
		const [draft] = reply.data.cards
		if (!draft) {
			const message = reply.data.errors[0]?.message ?? 'Nothing came back.'
			return setState({ step: 'error', picked, message, retry })
		}
		setState({ step: 'review', picked, row, draft })
	}

	const add = async (picked: Picked, row: GenerateRow, draft: CardDraft) => {
		const mine = ++run.current
		setState({ step: 'adding', picked, row, draft })
		const reply = await send({ type: 'add', req: { cards: [draft] } })
		if (mine !== run.current) return

		const retry = () => void add(picked, row, draft)
		if (!reply.ok) return setState(failed(picked, reply, retry))
		const [result] = reply.data.results
		if (!result) {
			const message = 'The server returned no result for this card.'
			return setState({ step: 'error', picked, message, retry })
		}
		setState({ step: 'done', picked, row, draft, result })
	}

	const start = (picked: Picked, kind: Kind) => {
		if (kind === 'as_is') {
			setState({ step: 'asIs', picked, text: picked.text })
			return
		}
		void generate(picked, {
			sourceId: crypto.randomUUID(),
			text: cleanWord(picked.text),
			kind,
			maxSenses: 1,
			context: picked.context || null,
		})
	}

	if (state.step === 'idle') return null

	if (state.step === 'pill') {
		const { picked } = state
		return (
			<div className="ankifier pill" style={pillPosition(picked.rect)}>
				<button type="button" onClick={() => start(picked, 'generated')}>
					Card
				</button>
				<button type="button" onClick={() => start(picked, 'as_is')}>
					As is
				</button>
			</div>
		)
	}

	const { picked } = state
	const word = 'row' in state ? state.row.text : picked.text
	const isAsIs =
		state.step === 'asIs' || ('row' in state && state.row.kind === 'as_is')

	return (
		<div
			className="ankifier panel"
			role="dialog"
			aria-label="Ankifier"
			style={panelPosition(picked.rect)}
		>
			<header>
				<strong className="word" title={word}>
					{word}
				</strong>
				{isAsIs && <span className="badge">as is</span>}
				{'draft' in state && state.draft.level && (
					<span className="badge">{state.draft.level}</span>
				)}
				<button
					type="button"
					className="close"
					aria-label="Close"
					onClick={close}
				>
					×
				</button>
			</header>

			{state.step === 'asIs' && (
				<>
					<p className="muted">
						Wrap what the card should hide in <code>[[…]]</code>, or leave
						it plain for a front/back card.
					</p>
					<textarea
						className="mono"
						aria-label="As-is text"
						rows={3}
						value={state.text}
						// eslint-disable-next-line jsx-a11y/no-autofocus -- the one thing to do next
						autoFocus
						onChange={(e) => setState({ ...state, text: e.target.value })}
						onKeyDown={(e) => {
							if (e.key === 'Enter' && (e.metaKey || e.ctrlKey))
								translate()
						}}
					/>
					<footer>
						<span className="spacer" />
						<button type="button" onClick={close}>
							Cancel
						</button>
						<button type="button" className="primary" onClick={translate}>
							Translate
						</button>
					</footer>
				</>
			)}

			{state.step === 'loading' && (
				<p className="status">
					<span className="spinner" />
					{state.row.kind === 'as_is' ? 'Translating…' : 'Writing a card…'}
				</p>
			)}

			{(state.step === 'review' || state.step === 'adding') && (
				<>
					{state.draft.senseDescription && state.row.kind === 'generated' && (
						<p className="muted sense">{state.draft.senseDescription}</p>
					)}
					<CardEditor
						draft={state.draft}
						onChange={(patch) =>
							state.step === 'review' &&
							setState({ ...state, draft: { ...state.draft, ...patch } })
						}
					/>
					<footer>
						<button
							type="button"
							disabled={state.step === 'adding'}
							onClick={() => void generate(picked, state.row)}
						>
							Regenerate
						</button>
						<span className="spacer" />
						<button type="button" onClick={close}>
							Discard
						</button>
						<button
							type="button"
							className="primary"
							disabled={state.step === 'adding'}
							onClick={() => void add(picked, state.row, state.draft)}
						>
							{state.step === 'adding' && <span className="spinner" />}
							{state.step === 'adding' ? 'Adding…' : 'Add to Anki'}
						</button>
					</footer>
				</>
			)}

			{state.step === 'done' && <Done result={state.result} onClose={close} />}

			{state.step === 'error' && (
				<>
					<p className="error">{state.message}</p>
					<footer>
						<span className="spacer" />
						<button type="button" onClick={close}>
							Close
						</button>
						<button type="button" className="primary" onClick={state.retry}>
							Retry
						</button>
					</footer>
				</>
			)}
		</div>
	)

	function translate() {
		if (state.step !== 'asIs' || !state.text.trim()) return
		void generate(state.picked, {
			sourceId: crypto.randomUUID(),
			text: state.text.trim(),
			kind: 'as_is',
			maxSenses: 1,
		})
	}
}

function Done({ result, onClose }: { result: AddResult; onClose: () => void }) {
	const { card, audio, deck } = result
	return (
		<>
			{card.state === 'ok' && <p className="ok">Added to {deck}.</p>}
			{card.state === 'skipped' && (
				<p className="warn">
					{card.detail === 'duplicate'
						? `Already in Anki (${deck}).`
						: (card.detail ?? 'Skipped.')}
				</p>
			)}
			{card.state === 'error' && <p className="error">{card.detail}</p>}
			{card.state === 'ok' && audio.state === 'error' && (
				<p className="warn">Added without audio: {audio.detail}</p>
			)}
			<footer>
				<span className="spacer" />
				<button type="button" onClick={onClose}>
					Close
				</button>
			</footer>
		</>
	)
}

function failed(
	picked: Picked,
	reply: Extract<Reply<unknown>, { ok: false }>,
	retry: () => void,
): State {
	// status 0 is the client's "fetch itself failed"; anything with a real
	// status carries the server's own `detail` (Anki down, a key missing).
	const message =
		reply.status === 0
			? "The Ankifier server isn't running. Start it with `poetry run ankifier`."
			: reply.message
	return { step: 'error', picked, message, retry }
}

const GAP = 6
const MARGIN = 8

function clampLeft(left: number, width: number): number {
	return Math.max(MARGIN, Math.min(left, window.innerWidth - width - MARGIN))
}

function pillPosition(rect: Rect): CSSProperties {
	const below = rect.bottom + GAP + 32 < window.innerHeight
	return {
		left: clampLeft(rect.left, 120),
		...(below
			? { top: rect.bottom + GAP }
			: { bottom: window.innerHeight - rect.top + GAP }),
	}
}

function panelPosition(rect: Rect): CSSProperties {
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
