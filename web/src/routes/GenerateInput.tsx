import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { api } from '../api/client'
import { Banner } from '../components/Banner'
import type { GenerateRow } from '../api/types'
import { emptyGenerateRow, useBatch } from '../store/batch'
import { rowActions } from '../lib/rows'
import { useAsyncAction } from '../lib/useAsyncAction'
import { useDebounced } from '../lib/useDebounced'

export function GenerateInput() {
	const navigate = useNavigate()
	const rows = useBatch((s) => s.generateRows)
	const setRows = useBatch((s) => s.setGenerateRows)
	const startWorking = useBatch((s) => s.startWorking)
	const setDrafts = useBatch((s) => s.setDrafts)
	const fail = useBatch((s) => s.fail)

	const { run, pending, error, setError } = useAsyncAction()
	const busy = pending !== null
	const {
		patch,
		add: addRow,
		remove: removeRow,
	} = rowActions(rows, setRows, emptyGenerateRow)
	const lastInput = useRef<HTMLInputElement | null>(null)

	// Text -> notes Anki already has for it, before any Mistral call. As-is rows
	// are whole sentences, not words, so they are not looked up.
	const [existing, setExisting] = useState<Record<string, number>>({})
	const words = useDebounced(
		useMemo(
			() => [...new Set(rows.filter((r) => !r.asIs).map((r) => r.text.trim()))],
			[rows],
		).filter(Boolean),
		400,
	)
	useEffect(() => {
		if (!words.length) return
		let cancelled = false
		api.existingWords(words)
			.then(({ results }) => {
				if (cancelled) return
				setExisting((prev) => ({
					...prev,
					...Object.fromEntries(results.map((r) => [r.text, r.notes])),
				}))
			})
			.catch(() => {
				/* a hint only: Anki may simply be closed */
			})
		return () => {
			cancelled = true
		}
	}, [words])

	const onKeyDown = (e: React.KeyboardEvent, index: number) => {
		if (e.key !== 'Enter') return
		// Enter adds a row rather than submitting -- submitting by accident costs
		// a batch of Mistral calls.
		e.preventDefault()
		if (index === rows.length - 1) {
			addRow()
			queueMicrotask(() => lastInput.current?.focus())
		}
	}

	const submit = async () => {
		const payload: GenerateRow[] = rows
			.filter((r) => r.text.trim())
			.map((r) => ({
				sourceId: r.id,
				text: r.text.trim(),
				kind: r.asIs ? 'as_is' : 'generated',
			}))

		if (!payload.length) {
			setError('Add at least one word.')
			return
		}

		startWorking('generate')
		await run(
			async () => {
				const { cards, errors } = await api.generate(payload)
				if (!cards.length && errors.length) {
					// Nothing to review, so stay here and say why.
					const message = errors
						.map((e) => `${e.text}: ${e.message}`)
						.join('\n')
					fail(message)
					setError(message)
					return
				}
				setDrafts(cards, errors)
				void navigate('/review')
			},
			{ onError: fail },
		)
	}

	return (
		<div className="panel">
			<h2>Words to generate</h2>
			<p className="intro">
				One word or phrase per row. Tick <strong>As is</strong> to keep the text
				exactly as typed — it is only translated, and any <code>[[…]]</code> you
				mark becomes the cloze deletion.
			</p>

			<div className="scroll">
				<table>
					<thead>
						<tr>
							<th className="grow">Word or phrase</th>
							<th>As is</th>
							<th />
						</tr>
					</thead>
					<tbody>
						{rows.map((row, i) => (
							<tr key={row.id}>
								<td>
									<input
										type="text"
										value={row.text}
										// Deliberate: puts the caret in the first row of an empty
										// form, which is the only thing to do on this screen.
										// eslint-disable-next-line jsx-a11y/no-autofocus
										autoFocus={i === 0 && rows.length === 1}
										ref={
											i === rows.length - 1
												? lastInput
												: undefined
										}
										placeholder="manger (verb)"
										onChange={(e) =>
											patch(row.id, { text: e.target.value })
										}
										onKeyDown={(e) => onKeyDown(e, i)}
									/>
									{!row.asIs && !!existing[row.text.trim()] && (
										<div className="small warn">
											Already in Anki: {existing[row.text.trim()]}{' '}
											note
											{existing[row.text.trim()] > 1
												? 's'
												: ''}{' '}
											with audio for this word.
										</div>
									)}
								</td>
								<td>
									<label className="check">
										<input
											type="checkbox"
											aria-label="As is"
											checked={row.asIs}
											onChange={(e) =>
												patch(row.id, {
													asIs: e.target.checked,
												})
											}
										/>
									</label>
								</td>
								<td>
									<button
										className="icon"
										onClick={() => removeRow(row.id)}
										aria-label="Remove row"
									>
										✕
									</button>
								</td>
							</tr>
						))}
					</tbody>
				</table>
			</div>

			{error && <Banner tone="error">{error}</Banner>}

			<div className="actions">
				<button onClick={addRow}>Add row</button>
				<span className="spacer" />
				<button className="primary" onClick={submit} disabled={busy}>
					{busy && <span className="spinner" />}
					{busy ? 'Generating…' : 'Generate'}
				</button>
			</div>

			{busy && (
				<p className="hint-line">
					Roughly two seconds per word —{' '}
					{rows.filter((r) => r.text.trim()).length} to go.
				</p>
			)}
		</div>
	)
}
