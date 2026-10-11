# Agents Guide — Bacon's Law

Correspondence trivia game (Six Degrees of Kevin Bacon). [README](README.md) has the concept and the
current tech decisions; this file is the working guide for changing the repo.

## Layout

Polyglot monorepo, two independent toolchains. Commands run from each subtree's root — there is **no
package manifest or code at the repo root**.

| Path | Stack | Toolchain |
|---|---|---|
| `etl/` | Python 3.14 — offline Wikidata graph build. The one finished component | `uv` |
| `ts/` | pnpm workspace: `packages/{engine,lib,scripts,tsconfig}`, `server`, `web` | `pnpm`, Node 24 |
| `docs/` | Conformance specs (see below) | — |

Current work is `packages/engine`, the round engine — plan in
[ts/docs/engine-impl.md](ts/docs/engine-impl.md). `server/` and `web/` are one-line stubs: no routes,
no UI, no framework installed. `web` is absent from `ts/tsconfig.json`'s project references and has no
`test` or `build` script.

Postgres runs from [docker-compose.yml](docker-compose.yml) in both development and deploy;
[ts/schema.sql](ts/schema.sql) is the schema. Hosting is DigitalOcean.

## Checks

Confirm these pass before calling a change done. Run `ts/` checks from `ts/`, `etl/` checks from `etl/`.

- **ts/** — `pnpm lint` (Biome), `pnpm typecheck`, `pnpm test` (Vitest). `pnpm lint:fix` autofixes.
  Biome exits 0 on warnings, so read the output: a clean exit is not a clean tree.
- **etl/** — `uv run ruff check`, `uv run ruff format --check .`, `uv run basedpyright`, `uv run pytest`.

Only `etl/` has CI ([.github/workflows/etl.yml](.github/workflows/etl.yml)). Nothing gates `ts/` but
this list.

## Authoritative specs

- [ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md) — round engine, rules R1–R17 + conformance suite.
- [MATCH_CONFORMANCE.md](docs/MATCH_CONFORMANCE.md) — match layer, rules M1–M16 + conformance suite.

These are language-agnostic and win over any implementation. When code and a spec disagree, the code is
the bug — fix the code, or flag the spec conflict; never silently diverge.

They also outrank the `movie-actor-chain-game` skill, which predates them and supplies vocabulary only.
Where the skill calls a rule open — repeats, turn timers, how "appeared in" is established — the specs
have since decided it.

## TypeScript workspace

- Packages are ESM (`"type": "module"`) built with TS project references. Relative imports carry the
  `.js` extension — `from "../models.js"`, not `"../models"` — and `verbatimModuleSyntax` requires
  `import type` for type-only imports.
- New package: `pnpm --filter @baconslaw/scripts new-package <name>`. It writes the package from the
  `packages/lib` template and adds the `ts/tsconfig.json` project reference. Don't hand-roll one.
- Package tsconfigs exclude only `src/**/*.test.ts` from `dist`. Any other non-shipping source —
  shared test fixtures, for instance — needs its own `exclude` entry.

## Conventions

- **Commits:** Conventional format — `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- **Edits require an explicit request.** Default to investigation and proposing diffs in chat. When an
  edit seems warranted, describe it and wait for the go-ahead. A prompt naming behavior to build or fix
  is that request — proceed under TDD below.

## Test-Driven Development

For prompted code changes, follow TDD unless the user says to skip it.

1. Write one failing test expressing the desired behavior; run it and confirm it fails on an assertion,
   not an import/setup error.
2. Write the minimum code to pass; run the test and the surrounding suite; confirm green.
3. Refactor with the suite green, then re-run.

Guardrails:

- Never weaken, skip, or delete a test to force a pass — fix the code. If the test itself looks wrong,
  stop and say so.
- Don't write implementation before the red run; the red step is what proves the test can fail.
- Show the red and green runs. Don't report a step you didn't execute.
- If the behavior is too unclear to test, ask first — that's a design question, not a coding one.

When implementing a `TC-nn` conformance case, keep the id in the test name so coverage stays traceable
to the spec.
