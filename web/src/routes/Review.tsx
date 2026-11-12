import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { needsCloze } from '@ankifier/api'

import { api } from '../api/client'
import { Banner } from '../components/Banner'
import { EmptyState } from '../components/EmptyState'
import { ReviewRow } from '../components/ReviewRow'
import type { CardDraft } from '../api/types'
import { keptDrafts, useBatch } from '../store/batch'
import { useAsyncAction } from '../lib/useAsyncAction'
import { useDebounced } from '../lib/useDebounced'

/** The first field Anki compares for duplicates, whichever note type it is. */
const frontOf = (d: CardDraft) => `${d.clozeSentence}\u0000${d.sentence}`

/**
 * One review table for all three kinds.
 *
 * There were two near-identical templates for this, because generated and
 * manual cards arrived by different routes. They are the same shape of thing by
 * the time they get here -- add_one() has always treated them identically -- so
 * `kind` only decides which columns are worth showing.
 */
export function Review() {
	const navigate = useNavigate()
	const drafts = useBatch((s) => s.drafts)
	const keep = useBatch((s) => s.keep)
	const errors = useBatch((s) => s.errors)
	const source = useBatch((s) => s.source)
	const toggleKeep = useBatch((s) => s.toggleKeep)
	const setAllKeep = useBatch((s) => s.setAllKeep)
	const updateDraft = useBatch((s) => s.updateDraft)
	const startAdding = useBatch((s) => s.startAdding)
	const setResults = useBatch((s) => s.setResults)
	const fail = useBatch((s) => s.fail)

	const { run, pending: busy, error, setError } = useAsyncAction<'dry' | 'real'>()

	const kept = keptDrafts({ drafts, keep })
	const showSenses = drafts.some((d) => d.kind === 'generated')
	const unclozed = kept.filter(needsCloze)

	// Id -> the front that was checked. A flag only counts while the front is
	// unchanged, so editing a duplicate clears it before the next check lands.
	const [duplicates, setDuplicates] = useState<Record<string, string>>({})
	const settled = useDebounced(drafts, 400)
	useEffect(() => {
		if (!settled.length) return
		let cancelled = false
		api.checkCards(settled)
			.then(({ duplicates: ids }) => {
				if (cancelled) return
				const byId = new Map(settled.map((d) => [d.id, d]))
				setDuplicates(
					Object.fromEntries(
						ids.flatMap((id) => {
							const d = byId.get(id)
							return d ? [[id, frontOf(d)] as const] : []
						}),
					),
				)
			})
			.catch(() => {
				/* cosmetic: the add skips duplicates itself */
			})
		return () => {
			cancelled = true
		}
	}, [settled])
	const isDuplicate = (d: CardDraft) => duplicates[d.id] === frontOf(d)
	const keptDuplicates = kept.filter(isDuplicate)

	const add = async (dryRun: boolean) => {
		if (!kept.length) {
			setError('Nothing is ticked.')
			return
		}
		if (unclozed.length) return
		startAdding()
		await run(
			async () => {
				const { results } = await api.addCards({ cards: kept, dryRun })
				setResults(results)
				void navigate('/results')
			},
			{ key: dryRun ? 'dry' : 'real', onError: fail },
		)
	}

	if (!drafts.length) {
		return <EmptyState>Nothing to review yet.</EmptyState>
	}

	return (
		<div className="panel">
			<h2>
				Review — {kept.length} of {drafts.length} selected
			</h2>
			<p className="intro">
				Click the spoken text, card front, back or tags to edit it. Tags are
				comma-separated and are added to the level and word-class tags. Editing
				the spoken text gives the card its own audio file — it never overwrites
				a card you have already made. A row marked{' '}
				<span className="badge neutral">reads the back</span> is spoken from its
				back text, so editing either edits both.
			</p>

			{errors.length > 0 && (
				<Banner tone="warn">
					{errors.length} row{errors.length > 1 ? 's' : ''} produced nothing
					and cannot be added:
					{errors.map((e) => (
						<div key={e.sourceId} className="small">
							<strong>{e.text}</strong> — {e.message}
						</div>
					))}
				</Banner>
			)}

			{unclozed.length > 0 && (
				<Banner tone="warn">
					{unclozed.length} card{unclozed.length > 1 ? 's have' : ' has'} no
					cloze because the hidden text was not found in the sentence. Mark it
					in the card front as <code>{'{{c1::text::hint}}'}</code>, or untick
					the card, before adding.
				</Banner>
			)}

			{keptDuplicates.length > 0 && (
				<Banner tone="warn">
					{keptDuplicates.length} card
					{keptDuplicates.length > 1 ? 's are' : ' is'} already in Anki and
					will be skipped without generating audio. Edit the card front to
					make it a new card, or untick it.
				</Banner>
			)}

			<div className="scroll">
				<table className="review-table">
					<thead>
						<tr>
							<th>Keep</th>
							<th>Word</th>
							{showSenses && <th>Sense</th>}
							<th className="spoken">Spoken text</th>
							<th className="front">Card front</th>
							<th className="back">Back</th>
							<th className="tags">Tags</th>
							{showSenses && <th>Level</th>}
						</tr>
					</thead>
					<tbody>
						{drafts.map((d) => (
							<ReviewRow
								key={d.id}
								draft={d}
								kept={!!keep[d.id]}
								duplicate={isDuplicate(d)}
								showSenses={showSenses}
								onToggle={() => toggleKeep(d.id)}
								onChange={(change) => updateDraft(d.id, change)}
							/>
						))}
					</tbody>
				</table>
			</div>

			{error && <Banner tone="error">{error}</Banner>}

			<div className="actions">
				<Link to={source === 'manual' ? '/manual' : '/'} className="button">
					Back
				</Link>
				<button onClick={() => setAllKeep(kept.length !== drafts.length)}>
					{kept.length === drafts.length ? 'Untick all' : 'Tick all'}
				</button>
				<span className="spacer" />
				<button
					onClick={() => add(true)}
					disabled={busy !== null || unclozed.length > 0}
				>
					{busy === 'dry' && <span className="spinner" />}
					Dry run
				</button>
				<button
					className="primary"
					onClick={() => add(false)}
					disabled={busy !== null || unclozed.length > 0}
				>
					{busy === 'real' && <span className="spinner" />}
					{busy === 'real' ? 'Adding…' : `Add ${kept.length} to Anki`}
				</button>
			</div>

			<p className="hint-line">
				<strong>Dry run</strong> checks decks, filenames and note types without
				writing to Anki or spending ElevenLabs credits.
			</p>
		</div>
	)
}
