import { expect, test } from './test'

test.beforeEach(async ({ page, api: _ }) => {
	await page.goto('/manual')
})

test.describe('with a slow preview', () => {
	test.use({ previewDelayMs: 1000 })

	test('a marked front becomes a cloze and a plain front a Basic card', async ({
		page,
		api,
	}) => {
		const fronts = page.getByPlaceholder('Il faut que tu [[sois:être]] là')
		const backs = page.getByPlaceholder('You have to be there')

		await fronts.nth(0).fill('Il faut que tu [[sois:être]] là')
		await backs.nth(0).fill('You have to be there')
		await page.getByRole('button', { name: 'Add row' }).click()
		await fronts.nth(1).fill('bonjour')
		await backs.nth(1).fill('hello')
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
		await page.getByPlaceholder('Il faut que tu [[sois:être]] là').fill('bonjour')
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
