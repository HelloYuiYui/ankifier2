/**
 * Where the Ankifier server is. The only setting the extension has.
 *
 * In storage.local rather than .sync: the server is on this machine, so a URL
 * synced to another computer would point at nothing there.
 */

import { browser } from 'wxt/browser'

export const DEFAULT_SERVER = 'http://127.0.0.1:8000'

const KEY = 'serverUrl'

export async function getServer(): Promise<string> {
	const stored = await browser.storage.local.get(KEY)
	const url = stored[KEY]
	return typeof url === 'string' && url ? url : DEFAULT_SERVER
}

export async function setServer(url: string): Promise<void> {
	await browser.storage.local.set({ [KEY]: url })
}

/**
 * host_permissions only cover this machine, and the worker cannot reach
 * anything else -- so catch it here with a message rather than as a network
 * error later.
 */
export function isLocalServer(url: string): boolean {
	try {
		const { protocol, hostname } = new URL(url)
		return protocol === 'http:' && ['127.0.0.1', 'localhost'].includes(hostname)
	} catch {
		return false
	}
}
