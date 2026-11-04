import { test as base, expect } from '@playwright/test'
import type { GenerateResponse } from '@ankifier/api'

import { type FakeApi, fakeApi } from './fakeApi'

interface Fixtures {
	/** What /api/generate answers. Set per file or per test with test.use(). */
	generated: GenerateResponse | undefined
	/** How long /api/cloze/preview takes to answer. */
	previewDelayMs: number
	api: FakeApi
}

export const test = base.extend<Fixtures>({
	generated: [undefined, { option: true }],
	previewDelayMs: [0, { option: true }],
	api: async ({ page, generated, previewDelayMs }, use) => {
		const api = await fakeApi(page, { generated, previewDelayMs })
		await use(api)
		// A request the fake does not know is a new endpoint the tests miss.
		expect(api.unexpected).toEqual([])
	},
})

export { expect }
