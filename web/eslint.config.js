import js from '@eslint/js'
import globals from 'globals'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import prettier from 'eslint-config-prettier'

export default tseslint.config(
  // Vite writes the built SPA into the Python package; never lint the bundle.
  { ignores: ['dist'] },

  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      // Type-aware: catches floating promises and unsafe `any` flow, which the
      // tsconfig's own strictness flags do not. Needs the project service below.
      tseslint.configs.recommendedTypeChecked,
      jsxA11y.flatConfigs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
      // Last, so it wins: switches off every rule that would fight Prettier.
      prettier,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: {
        // Resolves each file through tsconfig.app.json / tsconfig.node.json
        // rather than naming them here, which the project-references layout
        // would otherwise make awkward.
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      // The tsconfig already fails the build on unused locals and parameters,
      // so a second, differently-configured check only adds noise.
      '@typescript-eslint/no-unused-vars': 'off',

      // An async onClick is the normal way to run a request from a handler.
      // Only the attribute case is exempt; a promise passed anywhere else that
      // expects void is still an error.
      '@typescript-eslint/no-misused-promises': [
        'error',
        { checksVoidReturn: { attributes: false } },
      ],
    },
  },

  {
    // The one place untyped data enters: `response.json()` and the Vite env
    // are both `any`, and the code guards them by hand. Typing them properly
    // would be a change to the client, not to its lint config.
    files: ['src/api/client.ts'],
    rules: {
      '@typescript-eslint/no-unsafe-assignment': 'off',
      '@typescript-eslint/no-unsafe-member-access': 'off',
    },
  },

  // Build and config files run in Node, not the browser.
  {
    files: ['vite.config.ts', 'eslint.config.js'],
    languageOptions: { globals: globals.node },
  },
)
