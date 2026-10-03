import { createRoot } from 'react-dom/client'
import { createShadowRootUi } from 'wxt/utils/content-script-ui/shadow-root'
import { defineContentScript } from 'wxt/utils/define-content-script'

import { Bubble } from '../../src/Bubble'
import './style.css'

export default defineContentScript({
	matches: ['<all_urls>'],
	// style.css goes into the shadow root, not the page.
	cssInjectionMode: 'ui',

	async main(ctx) {
		const ui = await createShadowRootUi(ctx, {
			name: 'ankifier-bubble',
			position: 'inline',
			anchor: 'body',
			// Closed, so page scripts cannot reach in and click "Add to Anki":
			// that button spends credits and writes to the user's collection.
			mode: 'closed',
			// Keys typed into the bubble stay in it. Without this, a site's
			// single-key shortcuts (j/k, s, /) fire while editing a card.
			isolateEvents: true,
			onMount(container, _shadow, host) {
				const root = createRoot(container)
				root.render(<Bubble host={host} />)
				return root
			},
			onRemove(root) {
				root?.unmount()
			},
		})
		ui.mount()
	},
})
