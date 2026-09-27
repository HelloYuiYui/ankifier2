/**
 * The only part of the extension that calls the API.
 *
 * Why not the content script: its fetch() runs with the page's origin. The
 * server sends no CORS headers (it is off by default -- the server writes to
 * Anki and spends credits), and Chrome's Private Network Access rules block a
 * public page from calling localhost anyway. This worker has host_permissions
 * for 127.0.0.1/localhost, so neither applies to it, and the server's CORS
 * stays shut to every page on the web.
 */

import { ApiError, createClient } from '@ankifier/api'
import { browser } from 'wxt/browser'
import { defineBackground } from 'wxt/utils/define-background'

import type { Reply, Request } from '../src/messages'
import { getServer } from '../src/server'

async function handle(req: Request): Promise<unknown> {
	// Read per request, not once: the popup can change it at any time, and an
	// MV3 worker is restarted often enough that a cached value buys nothing.
	const api = createClient({ base: await getServer() })
	switch (req.type) {
		case 'health':
			return api.health()
		case 'generate':
			return api.generate([req.row])
		case 'add':
			return api.addCards(req.req)
	}
}

export default defineBackground(() => {
	browser.runtime.onMessage.addListener((message, _sender, sendResponse) => {
		handle(message as Request).then(
			(data) => sendResponse({ ok: true, data } satisfies Reply<unknown>),
			(e: unknown) =>
				sendResponse({
					ok: false,
					status: e instanceof ApiError ? e.status : -1,
					message: e instanceof Error ? e.message : String(e),
				} satisfies Reply<unknown>),
		)
		// Keeps the channel open for the async sendResponse above.
		return true
	})
})
