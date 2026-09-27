import { defineConfig } from 'wxt'

export default defineConfig({
	modules: ['@wxt-dev/module-react'],
	// Explicit imports, as in web/: auto-imported globals are invisible to a
	// reader and need a generated ESLint config to lint at all.
	imports: false,
	manifest: {
		name: 'Ankifier',
		description: 'Select a word on any page and turn it into an Anki card.',
		permissions: ['storage'],
		// The only origins the background worker may call. Match patterns ignore
		// the port, so these cover whatever port the server runs on -- and
		// nothing beyond this machine, since the server writes to Anki and
		// spends API credits.
		host_permissions: ['http://127.0.0.1/*', 'http://localhost/*'],
	},
})
