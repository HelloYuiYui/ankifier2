import js from '@eslint/js'
import globals from 'globals'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import reactHooks from 'eslint-plugin-react-hooks'
import tseslint from 'typescript-eslint'
import prettier from 'eslint-config-prettier'

// web/'s config, less react-refresh: there is no HMR boundary to protect in a
// content script.
export default tseslint.config(
	{ ignores: ['.output', '.wxt'] },

	{
		files: ['**/*.{ts,tsx}'],
		extends: [
			js.configs.recommended,
			tseslint.configs.recommendedTypeChecked,
			jsxA11y.flatConfigs.recommended,
			reactHooks.configs.flat.recommended,
			// Last, so it wins: switches off every rule that would fight Prettier.
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
			'@typescript-eslint/no-misused-promises': [
				'error',
				{ checksVoidReturn: { attributes: false } },
			],
		},
	},

	{
		files: ['wxt.config.ts', 'eslint.config.js'],
		languageOptions: { globals: globals.node },
	},
)
