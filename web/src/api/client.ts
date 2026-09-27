/**
 * The web app's API client; the implementation is shared in @ankifier/api.
 *
 * VITE_API_BASE is empty by default, which means same-origin -- through Vite's
 * proxy in dev, and directly in production where FastAPI serves this bundle.
 * Setting it is all that is needed to put the SPA on a CDN and the API
 * somewhere else.
 */

import { createClient } from '@ankifier/api'

export { ApiError } from '@ankifier/api'

const BASE: string = import.meta.env.VITE_API_BASE ?? ''

export const api = createClient({ base: BASE })
