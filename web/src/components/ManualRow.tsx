import type { AudioSide, ClozeResult, ManualRowInput } from '../api/types'
import { hasMarker, sideOf } from '../lib/manual'
import { ClozePreview } from './ClozePreview'
import { EditableCell } from './EditableCell'

export function ManualRow({
	row,
	preview,
	onChange,
	onRemove,
}: {
	row: ManualRowInput
	preview: ClozeResult | undefined
	onChange: (change: Partial<ManualRowInput>) => void
	onRemove: () => void
}) {
	return (
		<tr>
			<td>
				<EditableCell
					label="Front"
					placeholder="Il faut que tu [[sois:être]] là"
					value={row.front}
					onChange={(front) => onChange({ front })}
				/>
				{hasMarker(row.front) && (
					<div className="preview">
						{preview ? (
							<ClozePreview cloze={preview.cloze} />
						) : (
							<span className="muted">…</span>
						)}
					</div>
				)}
			</td>
			<td>
				<EditableCell
					label="Back"
					placeholder="You have to be there"
					value={row.back}
					onChange={(back) => onChange({ back })}
				/>
			</td>
			<td>
				<select
					aria-label="Audio from"
					value={sideOf(row)}
					onChange={(e) =>
						onChange({ audioSide: e.target.value as AudioSide })
					}
				>
					<option value="front">Front</option>
					<option value="back">Back</option>
				</select>
				{sideOf(row) === 'back' && !row.back.trim() && (
					<div className="small muted">No back text — no audio.</div>
				)}
			</td>
			<td>
				<button className="icon" onClick={onRemove} aria-label="Remove row">
					✕
				</button>
			</td>
		</tr>
	)
}
