import type { AudioSide, ClozeResult, ManualRowInput } from '../api/types'
import { hasMarker, sideOf } from '../lib/manual'
import { ClozePreview } from './ClozePreview'

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
				<textarea
					rows={1}
					value={row.front}
					placeholder="Il faut que tu [[sois:être]] là"
					onChange={(e) => onChange({ front: e.target.value })}
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
				<textarea
					rows={1}
					value={row.back}
					placeholder="You have to be there"
					onChange={(e) => onChange({ back: e.target.value })}
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
