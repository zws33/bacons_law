# TDD plan: `@baconslaw/engine` round engine

## Objective

Implement the round engine against [ENGINE_CONFORMANCE.md](../../docs/ENGINE_CONFORMANCE.md): R1–R17,
cases TC-01…TC-34 (there is no TC-32), structural S1–S3.

`src/models.ts` and `src/test-utils/fixtures.ts` are committed; both need the step-1 corrections first.

## Design decisions

1. **Two outcomes, no third.** `playMove` returns `InProgress | RoundOver`. There is no `Rejected`: a
   wrong-type move is a thrown programming error (R4, R15), and an unavailable move *ends the round*
   with `reason: "repeat"` (R5, R16) rather than bouncing.

2. **Typestate via overloads.** `InProgress` is a union of three variants on an `expecting` tag, each
   carrying the spec's persisted fields (`moves`, `currentPlayerIndex`, `playerCount`,
   `excludedActorIds`, `excludedMovieIds`): `AwaitingOpener` (`"any"`, empty chain, accepts either —
   R1), `AwaitingActor` (`"actor"`, last move a `Movie`), `AwaitingMovie` (`"movie"`, last move an
   `Actor`).

   ```ts
   function playMove(s: AwaitingActor, m: Actor): MoveOutcome;
   function playMove(s: AwaitingMovie, m: Movie): MoveOutcome;
   function playMove(s: AwaitingOpener, m: Move): MoveOutcome;
   function playMove(s: InProgress, m: Move): MoveOutcome; // widened impl
   ```

   R4 enforced statically, which the spec permits. The widened signature is the deserialized-caller
   path; its impl keeps the runtime type check and throws `WrongTypeError` — static enforcement
   relocates the check, it does not remove it.

   `expecting` is derived from `moves.at(-1)` in the constructor and never caller-settable, or the
   typestate can lie about the chain.

3. **Smart constructors + branded types** (R13). `createActor`, `createMovie`, `createInProgress`
   validate and throw at construction: non-blank `id`; non-blank members of `castIds` (an *empty*
   `castIds` is legal — TC-17, TC-23); `playerCount >= 2`; `0 <= currentPlayerIndex < playerCount`;
   exclusion sets default empty (TC-31). The brand is what makes R13 binding — without it
   `{ id: "", … }` satisfies `Actor`. Cost: every move crossing a wire boundary re-enters through a
   constructor.

4. **Errors thrown, never returned** (R15) — that split is what keeps them out of `MoveOutcome`.

   | Class | Raised by | Rule |
   |---|---|---|
   | `ValidationError` | a constructor | R13 |
   | `IllegalStateError` | `playMove`/`forfeit` on a `RoundOver` | R14 |
   | `WrongTypeError` | widened `playMove`, on an unexpected type | R4, R15 |

   Separate classes so a session layer maps `WrongTypeError` to a client fault and the others to a
   server fault. `IllegalStateError` is a defensive guard only — the narrow overloads make TC-24 a
   compile error.

5. **Order is R5 → R6: availability, then connection.** Type left the runtime path in decision 2. On an
   empty chain, run availability alone (R1 + R5, TC-30). Both-failing resolves to `Repeat` (TC-33).

6. **`ForfeitReason` is a proper subset of `RoundEndReason`.** `forfeit` accepts
   `"gaveUp" | "deadlineLapsed"`; `"unconnected"` must not compile (TC-34).

## Files to change (under `packages/engine/`)

| File | Contents |
|---|---|
| `src/errors.ts` | the three classes above |
| `src/models.ts` | *exists* — add R13 validation + brands to the constructors; drop the dead unexported `RoundEndReason`; export `Move` |
| `src/state.ts` | `InProgress` variants, `RoundOver`, `RoundEndReason`, `ForfeitReason`, `createInProgress()`, internal `roundOver()`, `expecting` derivation |
| `src/playMove.ts` | overloads + impl: R1–R3, R5, R6, R9, R11, R16 |
| `src/forfeit.ts` | `forfeit()`: R7, R8 |
| `src/index.ts` | *exists* — barrel |
| `src/test-utils/fixtures.ts` | *exists, two bugs* — `UNRELATED.castIds` must be `["Q99","Q1","Q98"]`; TC-14 is meaningless without `Q99`. `TWISTER.displayText` is `"Twister"`. Add `LONG_CHAIN` and typed helpers `opening()`, `expectingActor()`, `expectingMovie()`. Export everything: the 12 `noUnusedVariables` lint warnings are this file |

**tsconfig:** add `"src/test-utils"` to `exclude` — it excludes only `src/**/*.test.ts`, so fixtures
currently ship in `dist`.

**package.json:** `test` → `vitest run --typecheck`; drop `--passWithNoTests` after step 2.

Engine-specific conventions beyond [AGENTS.md](../../AGENTS.md): colocated `*.test.ts`, separate
`*.test-d.ts` for static cases, camelCase enum values (`"gaveUp"`, not `"gave_up"`) per the committed
`models.ts`.

## TDD ordering (red → green, per group)

1. **Fixtures** — the two bug fixes, `LONG_CHAIN`, state helpers. Prerequisite, not a test.
2. **Group G** `models.test.ts`, `state.test.ts`: TC-23, 21, 22, 31 → constructors, `ValidationError`.
   First, because everything constructs.
3. **Group A** `playMove.test.ts`: TC-08, 13, 01, 02, 25 → accept path, rotation (R9), opener (R1).
4. **Group B**: TC-03, 04, 14, 17 → R2/R3/R6/R11, `reason: "unconnected"`.
5. **Group C**: TC-05, 06, 11, 15, 16, 28, 29, 30, 31, 33 → R5 both clauses, per-type scoping,
   R5-before-R6. TC-09, 10, 20 → `playMove.test-d.ts`, plus one runtime `WrongTypeError` through the
   widened overload.
6. **Group D**: TC-07, 34; TC-24 static.
7. **Group E**: TC-12, 26, 27 → N-agnostic rotation, `loserIndex == currentPlayerIndex` at every index.
8. **Group F**: TC-18 (no mutation across accept / round-over / repeat / forfeit), TC-19 (determinism).
9. **Structural**: S1 — no runtime deps, no `node:*` in `src`. S2 — `EntityId = string`, no re-mapping.
   S3 — type test that `RoundOver` has no winner, score, or placement field.

Static-only cases: TC-09, 10, 20, 24, and TC-34's `"unconnected"` leg. Everything else is runtime.

## Validation

- `pnpm --filter @baconslaw/engine test` → runtime green and `.test-d.ts` assertions hold.
- `pnpm --filter @baconslaw/engine typecheck` → clean under strict TS.
- `pnpm lint` from `ts/` → zero warnings, not just exit 0.
- Every `TC-nn` id appears in exactly one test name, and every `RoundOver` case asserts both `reason`
  and that `chain` excludes the losing move.

## Risks

- **Vitest `--typecheck` under TS 7.** If unstable, fall back to a `tsconfig.test.json` including
  `*.test-d.ts` plus a `test:types` script running `tsc --noEmit`. The static cases must be
  machine-checked, not commented.
- **Overload selection on feed-back (TC-25, TC-26).** The loop narrows on the `InProgress` tag before
  replay; if the narrowed type will not select an overload without a cast, the variants need an explicit
  re-derivation helper.
- **Brands at the wire boundary.** `server/` does not exist, so nothing exercises deserialization. The
  widened overload and `WrongTypeError` assume a caller — revisit when it lands.
