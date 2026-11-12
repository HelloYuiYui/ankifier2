import { expect, test } from './test'

const file = (name: string, text: string) => ({
	name,
	mimeType: 'text/csv',
	buffer: Buffer.from(text, 'utf-8'),
})

test.beforeEach(async ({ page, api: _ }) => {
	await page.goto('/manual')
})

test('an imported CSV fills the manual table and reaches the request', async ({
	page,
	api,
}) => {
	// BOM, CRLF, a header, a quoted field holding a comma, a semicolon that is
	// just text, and a row with no front.
	const csv =
		'﻿Front,Back,Audio\r\n' +
		'Il faut que tu [[sois:être]] là; vraiment,You have to be there,front\r\n' +
		'"Oui, non","Yes, no"\r\n' +
		',orphan back\r\n'
	await page.getByLabel('CSV file').setInputFiles(file('cards.csv', csv))

	await expect(page.getByText('Imported 2 rows from cards.csv')).toContainText(
		'skipped 1 without a front',
	)
	const fronts = page.getByPlaceholder('Il faut que tu [[sois:être]] là')
	await expect(fronts).toHaveCount(2)
	await expect(fronts.nth(0)).toHaveValue('Il faut que tu [[sois:être]] là; vraiment')
	await expect(fronts.nth(1)).toHaveValue('Oui, non')
	const sides = page.getByLabel('Audio from')
	await expect(sides.nth(0)).toHaveValue('front')
	await expect(sides.nth(1)).toHaveValue('back')

	await page.getByRole('button', { name: 'Review' }).click()
	await page.getByRole('button', { name: 'Add 2 to Anki' }).click()
	await expect(page.getByRole('heading', { level: 2 })).toHaveText(
		'Added 2 of 2 to Anki',
	)

	expect(
		api.added[0].cards.map((c) => [c.clozeSentence, c.translation, c.audioSide]),
	).toEqual([
		[
			'Il faut que tu {{c1::sois::être}} là; vraiment',
			'You have to be there',
			'front',
		],
		['Oui, non', 'Yes, no', 'back'],
	])
})

test('a CSV with no fronts is reported and changes nothing', async ({ page }) => {
	await page.getByPlaceholder('Il faut que tu [[sois:être]] là').fill('déjà là')
	await page.getByLabel('CSV file').setInputFiles(file('empty.csv', ',only a back\n'))

	await expect(page.getByText('empty.csv has no rows with a front.')).toBeVisible()
	await expect(page.getByPlaceholder('Il faut que tu [[sois:être]] là')).toHaveValue(
		'déjà là',
	)
})
