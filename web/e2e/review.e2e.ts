import { generatedDraft } from './fakeApi'
import { expect, test } from './test'

// One card that matched and one whose hidden text Mistral could not place.
test.use({
	generated: {
		cards: [
			generatedDraft({}),
			generatedDraft({
				id: 'g#2',
				senseNumber: 2,
				word: 'arbre',
				sentence: "L'arbre pousse.",
				clozeSentence: "L'arbre pousse.",
				hiddenText: 'le arbre',
				hint: 'tree',
				translation: 'The tree grows.',
			}),
		],
		errors: [],
	},
})

test.beforeEach(async ({ page, api: _ }) => {
	await page.goto('/')
	await page.getByPlaceholder('manger (verb)').fill('arbre')
	await page.getByRole('button', { name: 'Generate' }).click()
	await expect(page).toHaveURL(/\/review$/)
})

const unclozedRow = (page: import('@playwright/test').Page) =>
	page.getByRole('row').filter({ hasText: 'The tree grows.' })

test('a generated card without a cloze blocks adding', async ({ page, api }) => {
	await expect(page.getByText('1 card has no cloze')).toBeVisible()
	await expect(unclozedRow(page).getByText('no cloze')).toBeVisible()
	await expect(page.getByRole('button', { name: 'Add 2 to Anki' })).toBeDisabled()
	await expect(page.getByRole('button', { name: 'Dry run' })).toBeDisabled()
	expect(api.added).toEqual([])
})

test('marking the cloze by hand unblocks it', async ({ page, api }) => {
	await unclozedRow(page).locator('button.cell.mono').click()
	const front = page.getByLabel('Card front')
	await front.fill("{{c1::L'arbre::the tree}} pousse.")
	await front.blur()

	await expect(page.getByText('1 card has no cloze')).toBeHidden()
	await page.getByRole('button', { name: 'Add 2 to Anki' }).click()
	await expect(page.getByRole('heading', { level: 2 })).toHaveText(
		'Added 2 of 2 to Anki',
	)
	expect(api.added[0].cards[1].clozeSentence).toBe(
		"{{c1::L'arbre::the tree}} pousse.",
	)
})

test('unticking the card unblocks the rest', async ({ page, api }) => {
	await unclozedRow(page).getByRole('checkbox').uncheck()

	await expect(page.getByText('1 card has no cloze')).toBeHidden()
	await page.getByRole('button', { name: 'Add 1 to Anki' }).click()
	await expect(page.getByRole('heading', { level: 2 })).toHaveText(
		'Added 1 of 1 to Anki',
	)
	expect(api.added[0].cards.map((c) => c.word)).toEqual(['glace'])
})
