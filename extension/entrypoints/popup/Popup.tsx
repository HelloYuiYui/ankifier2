/**
 * The toolbar popup: where the server is, and whether everything behind it is
 * ready. The same /api/health the web app's banner reads, so a missing key or a
 * closed Anki shows up here rather than as a failure on the first card.
 */

import type { HealthResponse } from '@ankifier/api'
import { useEffect, useState } from 'react'

import { type Reply, send } from '../../src/messages'
import { DEFAULT_SERVER, getServer, isLocalServer, setServer } from '../../src/server'

type Health =
	| { state: 'checking' }
	| { state: 'ok'; data: HealthResponse }
	| { state: 'down'; message: string }

export function Popup() {
	const [url, setUrl] = useState('')
	const [saved, setSaved] = useState('')
	const [health, setHealth] = useState<Health>({ state: 'checking' })

	const check = async () => {
		setHealth({ state: 'checking' })
		setHealth(toHealth(await send({ type: 'health' })))
	}

	useEffect(() => {
		void getServer().then((u) => {
			setUrl(u)
			setSaved(u)
		})
		// Not check(): the state already starts at 'checking'.
		void send({ type: 'health' }).then((reply) => setHealth(toHealth(reply)))
	}, [])

	const valid = isLocalServer(url)

	const save = async () => {
		if (!valid) return
		await setServer(url)
		setSaved(url)
		await check()
	}

	return (
		<main>
			<h1>Ankifier</h1>
			<p className="muted">
				Select a word on any page and click <strong>Card</strong>, or select a
				sentence and click <strong>As is</strong>.
			</p>

			<section>
				<label htmlFor="server">Server</label>
				<div className="row">
					<input
						id="server"
						value={url}
						placeholder={DEFAULT_SERVER}
						spellCheck={false}
						onChange={(e) => setUrl(e.target.value)}
						onKeyDown={(e) => e.key === 'Enter' && void save()}
					/>
					<button
						type="button"
						disabled={!valid || url === saved}
						onClick={save}
					>
						Save
					</button>
				</div>
				{!valid && (
					<p className="error">
						Must be http://127.0.0.1 or http://localhost.
					</p>
				)}
			</section>

			<section>
				<div className="row">
					<h2>Status</h2>
					<span className="spacer" />
					<button type="button" onClick={check}>
						Recheck
					</button>
				</div>
				<HealthView health={health} />
			</section>
		</main>
	)
}

function toHealth(reply: Reply<HealthResponse>): Health {
	if (reply.ok) return { state: 'ok', data: reply.data }
	return {
		state: 'down',
		message:
			reply.status === 0
				? 'Server not running. Start it with `poetry run ankifier`.'
				: reply.message,
	}
}

function HealthView({ health }: { health: Health }) {
	if (health.state === 'checking') return <p className="muted">Checking…</p>
	if (health.state === 'down') return <p className="error">{health.message}</p>

	const { anki, keys, decks, targetLang } = health.data
	return (
		<ul className="checks">
			<Check ok={anki.ok} label={anki.ok ? 'Anki' : `Anki: ${anki.error}`} />
			<Check ok={keys.mistral} label="Mistral key (AI_KEY)" />
			<Check ok={keys.elevenlabs} label="ElevenLabs key" />
			<li className="muted">
				{targetLang} · cards → {decks.generated}, as-is → {decks.asIs}
			</li>
		</ul>
	)
}

function Check({ ok, label }: { ok: boolean; label: string }) {
	return (
		<li className={ok ? 'ok' : 'error'}>
			{ok ? '✓' : '✗'} {label}
		</li>
	)
}
