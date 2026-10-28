import { describe, expect, it } from 'vitest'

import type { ManualRowInput } from '../api/types'
import { detectDelimiter, manualRowsFromCsv, parseCsv } from './csv'

let n = 0
const newRow = (): ManualRowInput => ({
	id: `r${n++}`,
	front: '',
	back: '',
	audioSide: 'back',
})
const pairs = (text: string) =>
	manualRowsFromCsv(text, newRow).rows.map((r) => [r.front, r.back, r.audioSide])

describe('detectDelimiter', () => {
	it('picks the separator used most on the first line', () => {
		expect(detectDelimiter('a,b\nc,d')).toBe(',')
		expect(detectDelimiter('a;b\nc;d')).toBe(';')
		expect(detectDelimiter('a\tb')).toBe('\t')
	})

	it('ignores separators inside quotes', () => {
		expect(detectDelimiter('"Oui, non, peut-être";yes')).toBe(';')
	})

	it('falls back to a comma', () => {
		expect(detectDelimiter('bonjour')).toBe(',')
	})
})

describe('parseCsv', () => {
	it('handles quotes, escaped quotes and newlines inside quotes', () => {
		expect(parseCsv('"Il a dit ""oui"", puis",x\n"deux\nlignes",y')).toEqual([
			['Il a dit "oui", puis', 'x'],
			['deux\nlignes', 'y'],
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
		expect(pairs('Audio;Back;Front\nfront;hello;bonjour')).toEqual([
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
