# TDD plan: `@baconslaw/engine` round engine

## Context

## Design decisions

1. **Typestate via `playMove` overloads.** `InProgress` is a discriminated union of three variants on
   an `expecting` tag, each carrying the spec's persisted fields (`moves`, `currentPlayerIndex`,
   `playerCount`, `excludedActorIds`, `excludedMovieIds`):
   - `AwaitingOpener` (`expecting:"any"`, empty chain) — accepts `Actor | Movie` (R1)
   - `AwaitingActor` (`expecting:"actor"`, last move a `Movie`) — accepts only `Actor`
   - `AwaitingMovie` (`expecting:"movie"`, last move an `Actor`) — accepts only `Movie`

   ```ts
   function playMove(s: AwaitingActor, m: Actor): MoveOutcome;
   function playMove(s: AwaitingMovie, m: Movie): MoveOutcome;
   function playMove(s: AwaitingOpener, m: Move): MoveOutcome;
   function playMove(s: InProgress, m: Move): MoveOutcome; // widened boundary/impl
   ```

   The narrow overloads make `playMove(awaitingMovie, someActor)` a compile error (TC-09/10/20). The
   widened signature is the **deserialization boundary** a wire caller uses; its impl **keeps the
   runtime type check** and returns `Rejected(WrongType)` — static enforcement relocates the check, it
   does not remove it (R4). `expecting` is an engine-internal discriminant derived from `moves.last()`
   by the constructor; it is redundant with `moves` (an idiom translation of the spec's implicit
   "required type").

2. **Smart constructors + branded types** make invalid states unrepresentable (R13). `actor()`,
   `movie()`, `inProgress()` validate and **throw at construction** (never deferred to `playMove`),
   returning branded types so a raw object literal is not assignable. Validation: non-blank `id`;
   non-blank members of `castIds` (empty `castIds` set is legal — TC-17/TC-23 last case);
   `playerCount >= 2`; `0 <= currentPlayerIndex < playerCount`. Exclusion sets default to empty (R5
   clause 2, TC-31).

3. **Outcomes are `kind`-tagged** so the three returned shapes are runtime-distinguishable:
   - `InProgress` `kind:"in_progress"`
   - `Rejected` `{ kind:"rejected"; reason:"wrong_type"|"repeat" }` — carries no state (R16)
   - `RoundOver` `{ kind:"round_over"; loserIndex; chain; losingMove: Move|null; reason:"unconnected"|"gave_up"|"deadline_lapsed" }` — **no winner field** (S3)

   `forfeit(state: InProgress, reason: ForfeitReason): RoundOver` where
   `ForfeitReason = "gave_up" | "deadline_lapsed"` is a proper subset of `RoundEndReason` — passing
   `"unconnected"` will not compile (TC-34 static note).

4. **Evaluation order is normative (R4→R5→R6): type, then availability, then connection.** On an empty
   chain, skip type + connection, run availability only (R1 + R5, TC-30). Errors are **thrown, never
   returned** — that thrown/returned split is what keeps them out of `MoveOutcome` (R15). Two error
   classes: `ValidationError` (R13 construction) and `IllegalStateError` (R14 terminal, defensive
   runtime guard on the widened boundary; the narrow overloads make TC-24 a compile error).

## Files to change (all under `packages/engine/`)

| File                          | Contents                                                                                                                                                                 |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `src/errors.ts`               | `ValidationError`, `IllegalStateError`                                                                                                                                   |
| `src/types.ts`                | `EntityId`, `Actor`, `Movie`, `Move`, brands; `InProgress` , `RoundOver`, `RoundState`;                                                                                  |
| `src/entities.ts`             | `actor()`, `movie()` smart constructors (R12, R13)                                                                                                                       |
| `src/state.ts`                | `inProgress()` (R13), internal `roundOver()` builder, `expecting` derivation                                                                                             |
| `src/playMove.ts`             | overloads + impl: R1–R6, R9, R11, R16, evaluation order                                                                                                                  |
| `src/forfeit.ts`              | `forfeit()`: R7, R8                                                                                                                                                      |
| `src/index.ts`                | barrel: re-export public API + types                                                                                                                                     |
| `src/conformance.fixtures.ts` | TC fixtures (`TOM_HANKS`…`APOLLO`, `LONG_CHAIN`) + typed state helpers `opening()`, `expectingActor()`, `expectingMovie()` for the static cases. Build-excluded (below). |

**tsconfig:** add `"src/**/*.fixtures.ts"` to `exclude` (mirrors the existing `src/**/*.test.ts`
exclusion) so shared test fixtures are not shipped in `dist`.

**package.json:** change `test` to `vitest run --typecheck` (runtime + type-level tests in one pass);
keep `test:watch`. Drop `--passWithNoTests` once real tests exist.

Follow existing conventions: flat one-module-per-feature layout + colocated `*.test.ts` (mirrors
`packages/lib/makeSearchKey.ts`/`.test.ts`); Biome formatting (double quotes, semicolons, trailing
commas, 2-space, 80 col); strict TS with `verbatimModuleSyntax` (use `import type`),
`exactOptionalPropertyTypes` (`imagePath?`/`releaseYear?`/`losingMove` modeled precisely),
`noUncheckedIndexedAccess`.

## TDD ordering (red → green, per group)

1. **Fixtures** — translate the fixture block once into `conformance.fixtures.ts` (prerequisite, not a test).
2. **Group G construction** (`entities.test.ts`, `state.test.ts`): TC-23, TC-21, TC-22, TC-31 →
   drives smart constructors + `ValidationError`. First, since everything depends on them.
3. **Group A** (`playMove.test.ts`): TC-08, TC-13, TC-01, TC-02, TC-25 → core `playMove` accept path,
   rotation (R9), opener (R1).
4. **Group B** (`playMove.test.ts`): TC-03, TC-04, TC-14, TC-17 → R2/R3/R6/R11, `RoundOver` with
   `losingMove` + `chain`-excludes-loser + `reason:"unconnected"`.
5. **Group C** (`playMove.test.ts` runtime; `playMove.test-d.ts` static): TC-05, TC-06, TC-11, TC-15,
   TC-16, TC-28, TC-29, TC-30, TC-31, TC-33 (runtime) → R5 both clauses, per-type scoping, precedence.
   TC-09, TC-10, TC-20 → **static** `@ts-expect-error` in `.test-d.ts`; plus one runtime
   `Rejected(WrongType)` test via the widened boundary overload.
6. **Group D** (`forfeit.test.ts`, `playMove.test.ts`): TC-07, TC-34 (runtime reason pass-through +
   static `@ts-expect-error` for `"unconnected"` in `forfeit.test-d.ts`), TC-32 (rejection leaves round
   unchanged, turn not advanced), TC-24 (static, `playMove.test-d.ts`).
7. **Group E** (`playMove.test.ts` + `forfeit.test.ts`): TC-12, TC-26, TC-27 → N-agnostic rotation +
   `loserIndex == currentPlayerIndex` at every index.
8. **Group F** (`playMove.test.ts`): TC-18 (no mutation across accept/round-over/reject/forfeit),
   TC-19 (determinism by value).
9. **Structural**: S1 — assert `package.json` declares no runtime deps and no `node:*` imports in
   `src` (grep/inspection). S2 — `EntityId = string`, opaque; no re-mapping (inspection). S3 — optional
   type-level test that `RoundOver` has no `winnerIndex`/`score`/placement field.

## Conformance coverage map

- Runtime `.test.ts`: TC-01–08, 11, 12, 14–19, 21–23, 25–34
- Type-level `.test-d.ts` (satisfied statically): TC-09, TC-10, TC-20, TC-24, and TC-34's
  `"unconnected"` rejection; TC-09/10/20 also get one runtime `WrongType` test at the widened boundary
- Structural (inspection/type test): S1, S2, S3

Every `RoundOver` case asserts `chain` excludes the losing move and `reason`; every `Rejected` case
asserts unchanged state (TC-32 pins this in full).

## Validation

- `pnpm --filter @baconslaw/engine test` → `vitest run --typecheck`: all runtime TCs green **and** `.test-d.ts` type assertions pass (TC-09/10/20/24 compile-error expectations hold).
- `pnpm --filter @baconslaw/engine typecheck` → `tsc --build`: package builds clean under strict TS.
- `pnpm lint` (Biome) clean at repo root.
- Spot-check traceability: every `TC-nn` id appears in exactly one test name.

## Risks

- **Vitest `--typecheck` under TS 7 (native compiler).** If type-testing tooling is unstable on TS7, fall back to a `tsconfig.test.json` that includes `*.test-d.ts` + a `test:types` script running `tsc --noEmit` for the static assertions. The static conformance cases must be machine-checked, not merely commented.
- **Overload ergonomics for `TC-25`/`TC-26` (feed-result-back).** The `InProgress` branch of `MoveOutcome` returns the union; the loop narrows on `kind === "in_progress"` before replay. Confirm the narrowed type still selects a `playMove` overload without a cast.
- **`expecting` discriminant is redundant with `moves`.** Keep it strictly derived in `inProgress()`; never let a caller set it independently, or the typestate can lie about the chain.
