/**
 * The whole on-page UI: the pill beside a selection, then the bubble that
 * generates, reviews and adds one card.
 *
 * Nothing persists. The server keeps no batch and neither does this -- closing
 * the bubble discards the card, exactly as unticking a row does in web/.
 */

import type { CardDraft, GenerateRow } from '@ankifier/api'
import { useCallback, useEffect, useReducer, useRef } from 'react'

import {
	AsIsStep,
	DoneStep,
	ErrorStep,
	Header,
	LoadingStep,
	Pill,
	ReviewStep,
} from './BubbleSteps'
import { idle, reducer } from './bubbleState'
import { cleanWord } from './context'
import { type Reply, type Request, send } from './messages'
import { panelPosition, pillPosition } from './position'
import type { Picked } from './selection'
import { useSelectionPill } from './useSelectionPill'

/** How long a successful add stays on screen before the bubble closes. */
const DONE_MS = 2500

export function Bubble({ host }: { host: HTMLElement }) {
	const [state, dispatch] = useReducer(reducer, idle)
	// Bumped by every request and by closing, so a reply that lands after the
	// user has moved on is dropped instead of reopening an old card.
	const run = useRef(0)

	const close = useCallback(() => {
		run.current++
		dispatch({ type: 'close' })
	}, [])

	useSelectionPill(host, state.step, dispatch)

	const addedOk = state.step === 'done' && state.result.card.state === 'ok'
	useEffect(() => {
		if (!addedOk) return
		const t = setTimeout(close, DONE_MS)
		return () => clearTimeout(t)
	}, [addedOk, close])

	/** Resolves to null when a newer request or a close has superseded it. */
	const request = async <R extends Request>(req: R) => {
		const mine = ++run.current
		const reply = await send(req)
		return mine === run.current ? reply : null
	}

	const fail = (reply: Extract<Reply<unknown>, { ok: false }>, retry: () => void) =>
		// status 0 is the client's "fetch itself failed"; anything with a real
		// status carries the server's own `detail` (Anki down, a key missing).
		dispatch({
			type: 'fail',
			message:
				reply.status === 0
					? "The Ankifier server isn't running. Start it with `poetry run ankifier`."
					: reply.message,
			retry,
		})

	const generate = async (picked: Picked, row: GenerateRow) => {
		dispatch({ type: 'load', picked, row })
		const reply = await request({ type: 'generate', row })
		if (!reply) return
		const retry = () => void generate(picked, row)
		if (!reply.ok) return fail(reply, retry)
		const [draft] = reply.data.cards
		if (!draft) {
			const { errors } = reply.data
			const message = errors[0]?.message ?? 'Nothing came back.'
			return dispatch({ type: 'fail', message, retry })
		}
		dispatch({ type: 'loaded', draft })
	}

	const add = async (draft: CardDraft) => {
		dispatch({ type: 'add' })
		const reply = await request({ type: 'add', req: { cards: [draft] } })
		if (!reply) return
		const retry = () => void add(draft)
		if (!reply.ok) return fail(reply, retry)
		const [result] = reply.data.results
		if (!result) {
			const message = 'The server returned no result for this card.'
			return dispatch({ type: 'fail', message, retry })
		}
		dispatch({ type: 'added', result })
	}

	if (state.step === 'idle') return null

	const { picked } = state

	if (state.step === 'pill') {
		return (
			<Pill
				style={pillPosition(picked.rect)}
				onCard={() =>
					void generate(picked, {
						sourceId: crypto.randomUUID(),
						text: cleanWord(picked.text),
						kind: 'generated',
						maxSenses: 1,
						context: picked.context || null,
					})
				}
				onAsIs={() => dispatch({ type: 'startAsIs' })}
			/>
		)
	}

	const row = 'row' in state ? state.row : undefined
	const draft = 'draft' in state ? state.draft : undefined

	const translate = (text: string) => {
		if (!text.trim()) return
		void generate(picked, {
			sourceId: crypto.randomUUID(),
			text: text.trim(),
			kind: 'as_is',
			maxSenses: 1,
		})
	}

	return (
		<div
			className="ankifier panel"
			role="dialog"
			aria-label="Ankifier"
			style={panelPosition(picked.rect)}
		>
			<Header
				word={row?.text ?? picked.text}
				asIs={state.step === 'asIs' || row?.kind === 'as_is'}
				draft={draft}
				onClose={close}
			/>

			{state.step === 'asIs' && (
				<AsIsStep
					text={state.text}
					onChange={(text) => dispatch({ type: 'editAsIs', text })}
					onTranslate={() => translate(state.text)}
					onCancel={close}
				/>
			)}

			{state.step === 'loading' && (
				<LoadingStep asIs={state.row.kind === 'as_is'} />
			)}

			{(state.step === 'review' || state.step === 'adding') && (
				<ReviewStep
					draft={state.draft}
					sense={
						state.row.kind === 'generated'
							? state.draft.senseDescription
							: null
					}
					adding={state.step === 'adding'}
					onChange={(change) => dispatch({ type: 'edit', change })}
					onRegenerate={() => void generate(picked, state.row)}
					onDiscard={close}
					onAdd={() => void add(state.draft)}
				/>
			)}

			{state.step === 'done' && (
				<DoneStep result={state.result} onClose={close} />
			)}

			{state.step === 'error' && (
				<ErrorStep
					message={state.message}
					onClose={close}
					onRetry={state.retry}
				/>
			)}
		</div>
	)
}
