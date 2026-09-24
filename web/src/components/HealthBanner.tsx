import { useEffect, useState } from 'react'

import { ApiError, api } from '../api/client'
import type { HealthResponse } from '../api/types'

/**
 * One call at boot, so the user learns that Anki is closed or a key is missing
 * here rather than halfway through a batch.
 */
export function HealthBanner() {
	const [health, setHealth] = useState<HealthResponse | null>(null)
	const [unreachable, setUnreachable] = useState<string | null>(null)

	useEffect(() => {
		api.health()
			.then((h) => {
				setHealth(h)
				setUnreachable(null)
			})
			.catch((e: unknown) =>
				setUnreachable(e instanceof ApiError ? e.message : String(e)),
			)
	}, [])

	if (unreachable) {
		return (
			<div className="banner error">
				{unreachable} Start it with <code>poetry run ankifier</code>.
			</div>
		)
	}

	if (!health) return null

	const problems: string[] = []
	if (!health.anki.ok) {
		problems.push(
			'Anki is not reachable — open Anki (with the AnkiConnect add-on) to add cards.',
		)
	}
	if (!health.keys.mistral) problems.push('AI_KEY is not set — generation will fail.')
	if (!health.keys.elevenlabs) {
		problems.push('ELEVEN_LABS_KEY is not set — audio will fail.')
	}

	if (!problems.length) return null

	return (
		<div className="banner warn">
			{problems.map((p) => (
				<div key={p}>{p}</div>
			))}
		</div>
	)
}
