/**
 * The contract between the content script (and popup) and the background worker.
 *
 * Only the worker calls the API -- see entrypoints/background.ts for why -- so
 * every request from a page goes through here. Replies are plain data: an Error
 * does not survive runtime messaging, so an ApiError arrives flattened into
 * `{ ok: false, status, message }`, with status 0 meaning the server is down.
 */

import type {
	AddRequest,
	AddResponse,
	GenerateResponse,
	GenerateRow,
	HealthResponse,
} from '@ankifier/api'
import { browser } from 'wxt/browser'

export type Request =
	| { type: 'health' }
	| { type: 'generate'; row: GenerateRow }
	| { type: 'add'; req: AddRequest }

/** What each request type resolves to. */
export interface Responses {
	health: HealthResponse
	generate: GenerateResponse
	add: AddResponse
}

export type Reply<T> =
	{ ok: true; data: T } | { ok: false; status: number; message: string }

/** Send a request to the worker. Never rejects: failures come back as a Reply. */
export async function send<R extends Request>(
	req: R,
): Promise<Reply<Responses[R['type']]>> {
	try {
		const reply = await browser.runtime.sendMessage<
			R,
			Reply<Responses[R['type']]> | undefined
		>(req)
		// undefined: the worker was torn down mid-request, or the extension
		// was reloaded under an open tab.
		return reply ?? { ok: false, status: -1, message: 'No reply from Ankifier.' }
	} catch {
		// Thrown by sendMessage itself when the extension was reloaded or
		// updated: this tab's content script is orphaned until a page reload.
		return {
			ok: false,
			status: -1,
			message: 'Ankifier was updated. Reload this page to use it.',
		}
	}
}
