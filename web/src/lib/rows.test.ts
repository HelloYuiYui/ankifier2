import { describe, expect, it } from 'vitest'

import { rowActions } from './rows'

type Row = { id: string; text: string }

const setup = (rows: Row[]) => {
	let current = rows
	let n = 0
	const actions = rowActions(
		rows,
		(next) => (current = next),
		() => ({ id: `new${n++}`, text: '' }),
	)
	return { actions, rows: () => current }
}

describe('rowActions', () => {
	it('patches only the row with that id', () => {
		const { actions, rows } = setup([
			{ id: 'a', text: 'x' },
			{ id: 'b', text: 'y' },
		])
		actions.patch('b', { text: 'z' })
		expect(rows()).toEqual([
			{ id: 'a', text: 'x' },
			{ id: 'b', text: 'z' },
		])
	})

	it('adds an empty row at the end', () => {
		const { actions, rows } = setup([{ id: 'a', text: 'x' }])
		actions.add()
		expect(rows()).toEqual([
			{ id: 'a', text: 'x' },
			{ id: 'new0', text: '' },
		])
	})

	it('replaces the last row with an empty one rather than leaving none', () => {
		const { actions, rows } = setup([{ id: 'a', text: 'x' }])
		actions.remove('a')
		expect(rows()).toEqual([{ id: 'new0', text: '' }])
	})
})
