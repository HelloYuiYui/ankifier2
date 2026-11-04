/**
 * Answers /api/* inside the browser, so the tests need no Python server, Anki,
 * Mistral or ElevenLabs. Typed against @ankifier/api, so a change to the wire
 * contract breaks these fixtures at typecheck rather than silently.
 */

import type {
	AddRequest,
	AddResponse,
	CardDraft,
	CheckResponse,
	ClozePreviewResponse,
	ClozeText,
	ExistingWordsResponse,
	GenerateResponse,
	HealthResponse,
} from '@ankifier/api'
import type { Page, Route } from '@playwright/test'

// The client builds these bodies inline, so the package has no type for them.
type ClozePreviewRequest = { texts: ClozeText[] }
type CheckRequest = { cards: CardDraft[] }
type ExistingWordsRequest = { texts: string[] }

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

export interface FakeOptions {
	/** What /api/generate answers. */
	generated?: GenerateResponse
	/** How long /api/cloze/preview takes to answer. */
	previewDelayMs?: number
	/** Card ids Anki already has. */
	duplicates?: string[]
	/** Input line -> notes Anki already has for it. */
	existingWords?: Record<string, number>
	/** Makes /api/cards/add answer 503 with this detail. */
	addFails?: string
}

export async function fakeApi(
	page: Page,
	{
		generated,
		previewDelayMs = 0,
		duplicates = [],
		existingWords = {},
		addFails,
	}: FakeOptions = {},
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

		if (path === '/api/cards/check') {
			const { cards } = request.postDataJSON() as CheckRequest
			const body: CheckResponse = {
				duplicates: cards
					.map((c) => c.id)
					.filter((id) => duplicates.includes(id)),
			}
			return json(route, body)
		}

		if (path === '/api/words/existing') {
			const { texts } = request.postDataJSON() as ExistingWordsRequest
			const body: ExistingWordsResponse = {
				results: texts.map((text) => ({
					text,
					notes: existingWords[text] ?? 0,
				})),
			}
			return json(route, body)
		}

		if (path === '/api/cards/add') {
			const req = request.postDataJSON() as AddRequest
			api.added.push(req)
			if (addFails)
				return route.fulfill({ status: 503, json: { detail: addFails } })
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
