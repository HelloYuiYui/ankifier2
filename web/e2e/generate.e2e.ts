import { expect, test } from './test'

test.use({ fake: { existingWords: { 'la glace': 2 } } })

test('a word Anki already has cards for is flagged before generating', async ({
	page,
	api: _,
}) => {
	await page.goto('/')
	const input = page.getByPlaceholder('manger (verb)')

	await input.fill('la glace')
	await expect(page.getByText('Already in Anki: 2 notes')).toBeVisible()

	await input.fill('le pain')
	await expect(page.getByText(/Already in Anki/)).toBeHidden()

	// An as-is row is a sentence, not a word, so it is never looked up.
	await input.fill('la glace')
	await page.getByRole('checkbox', { name: 'As is' }).check()
	await expect(page.getByText(/Already in Anki/)).toBeHidden()
})
