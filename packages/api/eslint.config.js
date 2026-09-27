import js from '@eslint/js'
import globals from 'globals'
import tseslint from 'typescript-eslint'
import prettier from 'eslint-config-prettier'

// The same type-aware base as web/, without the React plugins: nothing here
// renders.
export default tseslint.config(
	{
		files: ['**/*.ts'],
		extends: [
			js.configs.recommended,
			tseslint.configs.recommendedTypeChecked,
			prettier,
		],
		languageOptions: {
			globals: globals.browser,
			parserOptions: {
				projectService: true,
				tsconfigRootDir: import.meta.dirname,
			},
		},
		rules: {
			// tsc already fails on unused locals and parameters.
			'@typescript-eslint/no-unused-vars': 'off',
		},
	},
	{
		// `response.json()` is `any`; the client guards `detail` by hand.
		files: ['src/client.ts'],
		rules: {
			'@typescript-eslint/no-unsafe-assignment': 'off',
			'@typescript-eslint/no-unsafe-member-access': 'off',
		},
	},
	{
		files: ['eslint.config.js'],
		languageOptions: { globals: globals.node },
	},
)
