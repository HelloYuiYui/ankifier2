/** Edits for an input table that always keeps at least one row. */
export function rowActions<R extends { id: string }>(
	rows: R[],
	setRows: (rows: R[]) => void,
	emptyRow: () => R,
) {
	return {
		patch: (id: string, change: Partial<R>) =>
			setRows(rows.map((r) => (r.id === id ? { ...r, ...change } : r))),
		add: () => setRows([...rows, emptyRow()]),
		remove: (id: string) => {
			const kept = rows.filter((r) => r.id !== id)
			setRows(kept.length ? kept : [emptyRow()])
		},
	}
}
