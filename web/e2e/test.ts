import { test as base, expect } from '@playwright/test'

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
