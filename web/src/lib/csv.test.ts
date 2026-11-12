import { describe, expect, it } from 'vitest'

import type { ManualRowInput } from '../api/types'
import { manualRowsFromCsv, parseCsv } from './csv'

let n = 0
const newRow = (): ManualRowInput => ({
	id: `r${n++}`,
	front: '',
	back: '',
	audioSide: 'back',
})
const pairs = (text: string) =>
	manualRowsFromCsv(text, newRow).rows.map((r) => [r.front, r.back, r.audioSide])

describe('parseCsv', () => {
	it('handles quotes, escaped quotes and newlines inside quotes', () => {
		expect(parseCsv('"Il a dit ""oui"", puis",x\n"deux\nlignes",y')).toEqual([
			['Il a dit "oui", puis', 'x'],
			['deux\nlignes', 'y'],
		])
	})

	it('splits on commas only', () => {
		expect(parseCsv('Attends; je viens,Wait; I am coming\ta')).toEqual([
			['Attends; je viens', 'Wait; I am coming\ta'],
		])
	})

	it('handles CRLF, a BOM, a missing final newline and blank lines', () => {
		expect(parseCsv('\uFEFFa,b\r\n\r\nc,d')).toEqual([
			['a', 'b'],
			['c', 'd'],
		])
	})
})

describe('manualRowsFromCsv', () => {
	it('reads front, back and audio by position', () => {
		expect(pairs('Le [[chat]] dort,The cat sleeps,front\nbonjour,hello')).toEqual([
			['Le [[chat]] dort', 'The cat sleeps', 'front'],
			['bonjour', 'hello', 'back'],
		])
	})

	it('reads columns by name when there is a header', () => {
		expect(pairs('Audio,Back,Front\nfront,hello,bonjour')).toEqual([
			['bonjour', 'hello', 'front'],
		])
	})

	it('accepts a front-only file and keeps the default side for unknown values', () => {
		expect(pairs('bonjour\nmerci,thanks,sideways')).toEqual([
			['bonjour', '', 'back'],
			['merci', 'thanks', 'back'],
		])
	})

	it('skips and counts rows without a front', () => {
		const { rows, skipped } = manualRowsFromCsv(
			',orphan back\nbonjour,hello',
			newRow,
		)
		expect(rows).toHaveLength(1)
		expect(skipped).toBe(1)
	})

	it('gives every row its own id', () => {
		const { rows } = manualRowsFromCsv('a\nb', newRow)
		expect(new Set(rows.map((r) => r.id)).size).toBe(2)
	})
})
