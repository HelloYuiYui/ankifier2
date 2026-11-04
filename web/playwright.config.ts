import { defineConfig, devices } from '@playwright/test'

const PORT = 5179

export default defineConfig({
	testDir: 'e2e',
	// Not *.test.ts, which is vitest's.
	testMatch: '*.e2e.ts',
	forbidOnly: !!process.env.CI,
	// A test that needs a retry to pass is a bug, not a flake.
	retries: 0,
	reporter: process.env.CI ? [['list'], ['github']] : 'list',
	use: {
		baseURL: `http://127.0.0.1:${PORT}`,
		trace: 'retain-on-failure',
		// For a machine with its own Chromium and no `playwright install`.
		launchOptions: { executablePath: process.env.CHROMIUM_PATH || undefined },
	},
	projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
	// The dev server, not a build: every /api call is faked in the browser, so
	// the proxy to :8000 is never used and no backend has to run.
	webServer: {
		command: `vite --host 127.0.0.1 --port ${PORT} --strictPort`,
		url: `http://127.0.0.1:${PORT}`,
		reuseExistingServer: !process.env.CI,
	},
})
