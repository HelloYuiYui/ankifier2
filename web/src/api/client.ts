/**
 * The only place that talks to the API.
 *
 * VITE_API_BASE is empty by default, which means same-origin -- through Vite's
 * proxy in dev, and directly in production where FastAPI serves this bundle.
 * Setting it is all that is needed to put the SPA on a CDN and the API
 * somewhere else.
 */

import type {
  AddRequest,
  AddResponse,
  AudioPreviewResponse,
  ClozePreviewResponse,
  ClozeText,
  GenerateResponse,
  GenerateRow,
  HealthResponse,
} from './types'

const BASE = import.meta.env.VITE_API_BASE ?? ''

export class ApiError extends Error {
  // Declared rather than a constructor parameter property: the tsconfig sets
  // erasableSyntaxOnly, which rules out syntax that emits runtime code.
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { 'content-type': 'application/json' },
      ...init,
    })
  } catch {
    // fetch only rejects for network-level failures, which here means the
    // Python server is not running at all.
    throw new ApiError(0, 'Cannot reach the Ankifier server. Is it running?')
  }

  if (!response.ok) {
    // FastAPI puts the message in `detail`; fall back to the status text for
    // anything that is not a FastAPI error (a proxy error page, say).
    let detail = response.statusText
    try {
      const body = await response.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      /* not JSON -- keep the status text */
    }
    throw new ApiError(response.status, detail)
  }

  return response.json() as Promise<T>
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  health: () => request<HealthResponse>('/api/health'),

  decks: () => request<string[]>('/api/decks'),

  /** Batched: a whole table is one request, not one per row. */
  clozePreview: (texts: ClozeText[]) =>
    post<ClozePreviewResponse>('/api/cloze/preview', { texts }),

  /** Serial server-side, ~2s per row. Expect to wait. */
  generate: (rows: GenerateRow[]) => post<GenerateResponse>('/api/generate', { rows }),

  addCards: (req: AddRequest) => post<AddResponse>('/api/cards/add', req),

  /** Cheap to repeat: the file is content-addressed and reused. */
  audioPreview: (text: string, stem?: string) =>
    post<AudioPreviewResponse>('/api/audio/preview', { text, stem }),
}
