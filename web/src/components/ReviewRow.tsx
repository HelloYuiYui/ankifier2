import { needsCloze } from '@ankifier/api'

import type { CardDraft } from '../api/types'
import { ClozePreview } from './ClozePreview'
import { EditableCell } from './EditableCell'

export function ReviewRow({
	draft: d,
	kept,
	duplicate,
	showSenses,
	onToggle,
	onChange,
}: {
	draft: CardDraft
	kept: boolean
	duplicate: boolean
	showSenses: boolean
	onToggle: () => void
	onChange: (change: Partial<CardDraft>) => void
}) {
	const edit = (field: keyof CardDraft) => (value: string) =>
		onChange({ [field]: value })
	// Bound to whichever field is read aloud: a column called "Spoken text" that
	// showed the front of a back-read card would be a lie, and editing it would
	// change nothing.
	const spokenField = d.audioSide === 'back' ? 'translation' : 'sentence'

	return (
		<tr className={!kept ? 'dropped' : needsCloze(d) ? 'needs-cloze' : undefined}>
			<td>
				<input type="checkbox" checked={kept} onChange={onToggle} />
			</td>
			<td>
				<div>{d.word}</div>
				{d.kind !== 'generated' && (
					<span className="badge neutral">
						{d.kind === 'as_is' ? 'as is' : 'manual'}
					</span>
				)}
				{duplicate && <span className="badge skipped">already in Anki</span>}
			</td>
			{showSenses && <td className="small muted">{d.senseDescription || '—'}</td>}
			<td>
				<EditableCell
					label="Spoken text"
					value={d[spokenField]}
					onChange={edit(spokenField)}
				/>
				{d.audioSide === 'back' && (
					<span className="badge neutral">reads the back</span>
				)}
			</td>
			<td>
				<EditableCell
					label="Card front"
					className="mono"
					value={d.clozeSentence}
					onChange={edit('clozeSentence')}
				/>
				<ClozePreview cloze={d.clozeSentence} />
				{needsCloze(d) && <span className="badge skipped">no cloze</span>}
			</td>
			<td>
				<EditableCell
					label="Back"
					value={d.translation}
					onChange={edit('translation')}
				/>
			</td>
			<td className="small">
				<EditableCell
					label="Tags"
					value={d.extraTags ?? ''}
					onChange={edit('extraTags')}
				/>
			</td>
			{showSenses && (
				<td className="small muted">
					{d.level ?? 'not returned'}
					{d.partOfSpeech && (
						<div>
							<span className="badge neutral">{d.partOfSpeech}</span>
						</div>
					)}
					{d.gender && (
						<div>
							<span className="badge neutral">{d.gender}</span>
						</div>
					)}
				</td>
			)}
		</tr>
	)
}
