import { useState } from 'react'

import { ApiError } from '../api/client'

export const errorMessage = (e: unknown) =>
	e instanceof ApiError ? e.message : String(e)

/**
 * Busy and error state around a request started from a handler. `K` names what
 * is pending, for a screen with more than one button that can start one.
 */
export function useAsyncAction<K extends string = 'busy'>() {
	const [pending, setPending] = useState<K | null>(null)
	const [error, setError] = useState<string | null>(null)

	const run = async (
		action: () => Promise<void>,
		{
			key = 'busy' as K,
			onError,
		}: { key?: K; onError?: (message: string) => void } = {},
	) => {
		setPending(key)
		setError(null)
		try {
			await action()
		} catch (e) {
			const message = errorMessage(e)
			setError(message)
			onError?.(message)
		} finally {
			setPending(null)
		}
	}

	return { run, pending, error, setError }
}
