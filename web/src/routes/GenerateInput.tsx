import { useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError, api } from '../api/client'
import type { GenerateRow, GenerateRowInput } from '../api/types'
import { emptyGenerateRow, useBatch } from '../store/batch'
import PanelHeader from '../components/common/PanelHeader'
import PANEL_CONSTANTS from '../components/common/panelConstants'

export function GenerateInput() {
	const navigate = useNavigate()
	const rows = useBatch((s) => s.generateRows)
	const setRows = useBatch((s) => s.setGenerateRows)
	const startWorking = useBatch((s) => s.startWorking)
	const setDrafts = useBatch((s) => s.setDrafts)
	const fail = useBatch((s) => s.fail)

	const [busy, setBusy] = useState(false)
	const [error, setError] = useState<string | null>(null)
	const lastInput = useRef<HTMLInputElement | null>(null)

	const patch = (id: string, change: Partial<GenerateRowInput>) =>
		setRows(rows.map((r) => (r.id === id ? { ...r, ...change } : r)))

	const addRow = () => setRows([...rows, emptyGenerateRow()])

	const removeRow = (id: string) => {
		const kept = rows.filter((r) => r.id !== id)
		setRows(kept.length ? kept : [emptyGenerateRow()])
	}

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

		setBusy(true)
		setError(null)
		startWorking('generate')
		try {
			const { cards, errors } = await api.generate(payload)
			if (!cards.length && errors.length) {
				// Nothing to review, so stay here and say why.
				fail(errors.map((e) => `${e.text}: ${e.message}`).join('\n'))
				setError(errors.map((e) => `${e.text}: ${e.message}`).join('\n'))
				return
			}
			setDrafts(cards, errors)
			void navigate('/review')
		} catch (e) {
			const message = e instanceof ApiError ? e.message : String(e)
			fail(message)
			setError(message)
		} finally {
			setBusy(false)
		}
	}

	return (
		<div className="panel">
			<PanelHeader
				title={PANEL_CONSTANTS.generateTitle}
				description={PANEL_CONSTANTS.generateDescription}
			/>

			<div className="scroll">
				<table>
					<thead>
						<tr>
							<th style={{ width: '100%' }}>Word or phrase</th>
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

			{error && (
				<div className="banner error" style={{ marginTop: 14 }}>
					{error}
				</div>
			)}

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
