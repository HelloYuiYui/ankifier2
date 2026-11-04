/**
 * Answers /api/* inside the browser, so the tests need no Python server, Anki,
 * Mistral or ElevenLabs. Typed against @ankifier/api, so a change to the wire
 * contract breaks these fixtures at typecheck rather than silently.
 */

import type {
	AddRequest,
	AddResponse,
	CardDraft,
	ClozePreviewResponse,
	ClozeText,
	GenerateResponse,
	HealthResponse,
} from '@ankifier/api'
import type { Page, Route } from '@playwright/test'

// The client builds this body inline, so the package has no type for it.
type ClozePreviewRequest = { texts: ClozeText[] }

export interface FakeApi {
	/** Every /api/cards/add body, in order. */
	added: AddRequest[]
	/** Paths the fake has no answer for. Asserted empty after each test. */
	unexpected: string[]
}

export const health: HealthResponse = {
	anki: { ok: true, version: 6, error: null },
	keys: { mistral: true, elevenlabs: true },
	decks: {
		generated: 'French::Vocabulary',
		asIs: 'French::Grammar',
		manual: 'French::Vocabulary',
		bulgarian: 'Bulgarian',
	},
	targetLang: 'French',
	ankiDecks: ['French::Vocabulary', 'French::Grammar', 'Bulgarian'],
}

const MARKER_RE = /\[\[(.+?)\]\]/g

/** Enough of cloze.render for the tests: `[[word:hint]]` -> `{{c1::word::hint}}`. */
function render(text: string): { plain: string; cloze: string } {
	const cloze = text.replace(MARKER_RE, (_, body: string) => {
		const [word, ...hint] = body.split(':')
		return hint.length ? `{{c1::${word}::${hint.join(':')}}}` : `{{c1::${word}}}`
	})
	const plain = text.replace(MARKER_RE, (_, body: string) => body.split(':')[0])
	return { plain, cloze }
}

export function generatedDraft(overrides: Partial<CardDraft>): CardDraft {
	return {
		id: 'g#1',
		sourceId: 'g',
		kind: 'generated',
		word: 'glace',
		senseNumber: 1,
		senseDescription: 'ice',
		sentence: 'La glace fond.',
		clozeSentence: '{{c1::La glace::ice}} fond.',
		translation: 'The ice melts.',
		hiddenText: 'La glace',
		hint: 'ice',
		level: 'A2',
		audioStem: null,
		audioSide: 'front',
		...overrides,
	}
}

export async function fakeApi(
	page: Page,
	{
		generated,
		previewDelayMs = 0,
	}: { generated?: GenerateResponse; previewDelayMs?: number } = {},
): Promise<FakeApi> {
	const api: FakeApi = { added: [], unexpected: [] }
	const json = (route: Route, body: unknown) => route.fulfill({ json: body })

	// A predicate, not '**/api/**': that glob also catches Vite's module URLs
	// such as /src/api/client.ts, and the app would never load.
	const isApi = (url: URL) => url.pathname.startsWith('/api/')
	await page.route(isApi, async (route) => {
		const request = route.request()
		const path = new URL(request.url()).pathname

		if (path === '/api/health') return json(route, health)

		if (path === '/api/cloze/preview') {
			await new Promise((resolve) => setTimeout(resolve, previewDelayMs))
			const { texts } = request.postDataJSON() as ClozePreviewRequest
			const body: ClozePreviewResponse = {
				results: texts.map((t) => ({ id: t.id, ...render(t.text) })),
			}
			return json(route, body)
		}

		if (path === '/api/generate' && generated) return json(route, generated)

		if (path === '/api/cards/add') {
			const req = request.postDataJSON() as AddRequest
			api.added.push(req)
			const body: AddResponse = {
				results: req.cards.map((c) => ({
					id: c.id,
					audio: { state: 'ok', detail: null },
					card: { state: 'ok', detail: null },
					deck: 'French::Vocabulary',
					audioUrl: null,
				})),
			}
			return json(route, body)
		}

		api.unexpected.push(`${request.method()} ${path}`)
		return route.fulfill({ status: 404, json: { detail: 'not faked' } })
	})

	return api
}
