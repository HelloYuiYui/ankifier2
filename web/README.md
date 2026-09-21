# web

The Ankifier SPA: React + TypeScript, built by Vite.

This package is a member of the pnpm workspace at the repo root, so install from
there (`pnpm install`), not from here. Every script below can be run either as
`pnpm --filter web <script>` from the root or as `pnpm <script>` from this
directory.

```bash
pnpm dev             # :5173, proxies /api to the Python server on :8000
pnpm build           # writes the bundle into ../src/ankifier/static/
pnpm preview         # serves that build

pnpm format          # prettier, writes
pnpm format:check    # prettier, reports (this is what CI runs)
pnpm lint            # eslint
pnpm lint:fix        # eslint --fix
pnpm typecheck       # tsc -b --noEmit
```

## Linting and formatting

Prettier owns formatting; `eslint-config-prettier` is last in the ESLint config
and switches off every rule that would disagree with it, so the two never argue
over the same line. Prettier is configured to the style the code was already
written in — no semicolons, single quotes, 88 columns, matching Ruff's width on
the Python side.

ESLint is **type-aware** (`recommendedTypeChecked`): it resolves each file
through the tsconfig, which makes it slower than a syntax-only linter but lets
it see unawaited promises and `any` leaking out of untyped data. Two deliberate
settings in `eslint.config.js`:

- `no-misused-promises` exempts JSX attributes, because an `async` `onClick` is
  the normal way to run a request from a handler.
- `src/api/client.ts` relaxes the `no-unsafe-*` rules. It is the one place
  untyped data enters — `response.json()` and `import.meta.env` are both `any`
  — and the code guards them by hand.

`no-unused-vars` is off because `tsconfig.app.json` already sets
`noUnusedLocals` and `noUnusedParameters`, which fail the build instead.

The build output in `../src/ankifier/static/` is generated and never linted or
committed.
