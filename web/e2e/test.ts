import { type Page, test as base, expect } from '@playwright/test'

import { type FakeApi, type FakeOptions, fakeApi } from './fakeApi'

interface Fixtures {
	/** Set per file or per test with test.use({ fake: {...} }). */
	fake: FakeOptions
	api: FakeApi
}

export const test = base.extend<Fixtures>({
	fake: [{}, { option: true }],
	api: async ({ page, fake }, use) => {
		const api = await fakeApi(page, fake)
		await use(api)
		// A request the fake does not know is a new endpoint the tests miss.
		expect(api.unexpected).toEqual([])
	},
})

export { expect }

type Column = 'Front' | 'Back'

/** The manual table's cell, as it reads when it is not being edited. */
export const manualCell = (page: Page, row: number, column: Column) =>
	page
		.locator('tbody tr')
		.nth(row)
		.locator('td')
		.nth(column === 'Front' ? 0 : 1)
		.locator('button.cell')

export async function fillManualCell(
	page: Page,
	row: number,
	column: Column,
	text: string,
) {
	await manualCell(page, row, column).click()
	const box = page.getByLabel(column, { exact: true })
	await box.fill(text)
	await box.blur()
}
