import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { HealthResponse } from '../api/types'
import { errorMessage } from './useAsyncAction'

// Shared by every caller, so the banner and the deck names cost one request.
// Cleared on failure, so the next mount tries again.
let request: Promise<HealthResponse> | null = null

export function useHealth() {
	const [health, setHealth] = useState<HealthResponse | null>(null)
	const [error, setError] = useState<string | null>(null)

	useEffect(() => {
		let live = true
		request ??= api.health()
		request
			.then((h) => {
				if (live) setHealth(h)
			})
			.catch((e: unknown) => {
				request = null
				if (live) setError(errorMessage(e))
			})
		return () => {
			live = false
		}
	}, [])

	return { health, error }
}
