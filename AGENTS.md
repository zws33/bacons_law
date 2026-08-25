# Agents Guide — Bacon's Law

Correspondence trivia game (Six Degrees of Kevin Bacon). [README](README.md) has the concept and the
current tech decisions; this file is the working guide for changing the repo.

## Layout

Polyglot monorepo, two independent toolchains. Commands run from each subtree's root — there is **no
package manifest or code at the repo root**.

| Path | Stack | Toolchain |
|---|---|---|
| `etl/` | Python 3.14 — offline Wikidata graph build | `uv` |
| `ts/` | pnpm workspace: `server`, `web`, `packages/*` (`lib`, `scripts`, `tsconfig`) | `pnpm`, Node 24 |
| `docs/` | Conformance specs (see below) | — |

## Checks

Confirm these pass before calling a change done. Run `ts/` checks from `ts/`, `etl/` checks from `etl/`.

- **ts/** — `pnpm lint` (Biome), `pnpm typecheck`, `pnpm test` (Vitest). `pnpm lint:fix` autofixes.
- **etl/** — `uv run ruff check`, `uv run basedpyright`, `uv run pytest`.

## Authoritative specs

- [ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md) — round engine, rules R1–R17 + conformance suite.
- [MATCH_CONFORMANCE.md](docs/MATCH_CONFORMANCE.md) — match layer, rules M1–M16 + conformance suite.

These are language-agnostic and win over any implementation. When code and a spec disagree, the code is
the bug — fix the code, or flag the spec conflict; never silently diverge.

## Conventions

- **Commits:** Conventional format — `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- **Edits require an explicit request.** Default to investigation and proposing diffs in chat. When an
  edit seems warranted, describe it and wait for the go-ahead.

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
