import type { AudioSide, ManualRowInput } from '../api/types'

/** RFC 4180: quoted fields may hold the separator, newlines and `""`. */
export function parseCsv(text: string, delimiter = ','): string[][] {
	const rows: string[][] = []
	let row: string[] = []
	let field = ''
	let quoted = false
	const src = text.replace(/^\uFEFF/, '')

	const endRow = () => {
		row.push(field)
		if (row.some((cell) => cell.trim())) rows.push(row)
		row = []
		field = ''
	}

	for (let i = 0; i < src.length; i++) {
		const ch = src[i]
		if (quoted) {
			if (ch === '"' && src[i + 1] === '"') {
				field += '"'
				i++
			} else if (ch === '"') quoted = false
			else field += ch
		} else if (ch === '"') quoted = true
		else if (ch === delimiter) {
			row.push(field)
			field = ''
		} else if (ch === '\n') endRow()
		else if (ch !== '\r') field += ch
	}
	endRow()
	return rows
}

const asSide = (value: string | undefined): AudioSide | undefined => {
	const v = value?.trim().toLowerCase()
	return v === 'front' || v === 'back' ? v : undefined
}

/**
 * Columns are front, back and an optional audio side, by position, or by name
 * when the first row is a header naming them.
 */
export function manualRowsFromCsv(
	text: string,
	newRow: () => ManualRowInput,
): { rows: ManualRowInput[]; skipped: number } {
	const table = parseCsv(text)
	let columns = { front: 0, back: 1, audio: 2 }

	const header = table[0]?.map((cell) => cell.trim().toLowerCase())
	const isHeader =
		header?.includes('front') &&
		header.every((cell) => ['front', 'back', 'audio', ''].includes(cell))
	if (header && isHeader) {
		const at = (name: string) => header.indexOf(name)
		columns = { front: at('front'), back: at('back'), audio: at('audio') }
		table.shift()
	}

	const rows: ManualRowInput[] = []
	let skipped = 0
	for (const cells of table) {
		const front = (cells[columns.front] ?? '').trim()
		if (!front) {
			skipped++
			continue
		}
		const row = newRow()
		rows.push({
			...row,
			front,
			back: (cells[columns.back] ?? '').trim(),
			audioSide: asSide(cells[columns.audio]) ?? row.audioSide,
		})
	}
	return { rows, skipped }
}
