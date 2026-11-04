import { expect, fillManualCell, test } from './test'

test.beforeEach(async ({ page, api: _ }) => {
	await page.goto('/manual')
})

test.describe('with a slow preview', () => {
	test.use({ fake: { previewDelayMs: 1000 } })

	test('a marked front becomes a cloze and a plain front a Basic card', async ({
		page,
		api,
	}) => {
		await fillManualCell(page, 0, 'Front', 'Il faut que tu [[sois:être]] là')
		await fillManualCell(page, 0, 'Back', 'You have to be there')
		await page.getByRole('button', { name: 'Add row' }).click()
		await fillManualCell(page, 1, 'Front', 'bonjour')
		await fillManualCell(page, 1, 'Back', 'hello')
		// The debounced preview is still in flight here: Review must fetch its own
		// render rather than let the raw [[...]] text through.
		await page.getByRole('button', { name: 'Review' }).click()

		await expect(page).toHaveURL(/\/review$/)
		await expect(page.getByRole('heading', { level: 2 })).toContainText(
			'2 of 2 selected',
		)

		await page.getByRole('button', { name: 'Add 2 to Anki' }).click()
		await expect(page.getByRole('heading', { level: 2 })).toHaveText(
			'Added 2 of 2 to Anki',
		)

		const [request] = api.added
		expect(request.dryRun).toBeFalsy()
		expect(
			request.cards.map((c) => [
				c.kind,
				c.sentence,
				c.clozeSentence,
				c.translation,
			]),
		).toEqual([
			[
				'manual',
				'Il faut que tu sois là',
				'Il faut que tu {{c1::sois::être}} là',
				'You have to be there',
			],
			['manual', 'bonjour', 'bonjour', 'hello'],
		])
	})
})

for (const [label, language, deckTarget] of [
	['French::Vocabulary', 'french', 'vocabulary'],
	['French::Grammar', 'french', 'grammar'],
	['Bulgarian', 'bulgarian', null],
] as const) {
	test(`the ${label} deck toggle reaches the request`, async ({ page, api }) => {
		await page.getByRole('radio', { name: label }).click()
		await expect(page.getByRole('radio', { name: label })).toBeChecked()
		await fillManualCell(page, 0, 'Front', 'bonjour')
		await page.getByRole('button', { name: 'Review' }).click()
		await page.getByRole('button', { name: 'Add 1 to Anki' }).click()
		await expect(page.getByRole('heading', { level: 2 })).toHaveText(
			'Added 1 of 1 to Anki',
		)

		const [card] = api.added[0].cards
		expect(card.language).toBe(language)
		expect(card.deckTarget ?? null).toBe(deckTarget)
	})
}

test('Tab moves from the front straight into editing the back', async ({ page }) => {
	await page.getByRole('button', { name: 'Il faut que tu [[sois:être]] là' }).click()
	await page.keyboard.type('bonjour')
	await page.keyboard.press('Tab')
	await page.keyboard.type('hello')
	await page.keyboard.press('Tab')

	const row = page.locator('tbody tr').first()
	await expect(row.locator('button.cell').nth(0)).toHaveText('bonjour')
	await expect(row.locator('button.cell').nth(1)).toHaveText('hello')
})
