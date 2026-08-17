# Build order

**Sequencing intent, not status.** Nothing here records progress, and no file in this repo does. This
document amends no decision — [DECISIONS.md](DECISIONS.md) owns those, and where the two disagree the
ADR wins.

**State at writing (2026-08-17):** `etl/` is the only code in the tree. `server/` and the web client
are unstarted. Hosting is the only open decision.

## Ordered steps

| # | Step | Done when |
|---|---|---|
| 0 | **ETL `v2`** — surface actor sitelink counts through `Edge` into `entities`; add an actor disambiguator | `transform && emit` produce `v2` and [etl/README.md](../etl/README.md)'s verify script passes |
| 1 | **Store spike, which becomes the loader** ([ADR 026](DECISIONS.md) item 4). Supabase project in a chosen region; load `v2` into its own schema; derive folded word-start keys in TypeScript at load | Storage consumed, typeahead p50 same-region, and word-start row count are measured numbers, not estimates |
| 2 | **Decide hosting; deploy a walking skeleton** — Fastify, JWKS verification, `suggest`, health; a web page that signs in by magic link and types into a typeahead | A deployed page resolves a name against a deployed server against Supabase |
| 3 | **Round engine and match layer**, pure TypeScript | The engine suite's Groups A–G and MC-01–32 pass |
| 4 | **Session layer** — Game entity and schema, CAS on `version`, `deadline_at` checked on the submit path, `ConnectionChecker` over Postgres, the transport-agnostic move pipeline, notification events emitted into a no-op consumer | Two signed-in players complete a match end to end |
| 5 | **Client game view; playtest** | Real players complete matches. This is what [ADR 019](DECISIONS.md) and [ADR 020](DECISIONS.md) are both waiting on — neither revisit trigger is observable before it |
| 6 | **Sweeper and transactional email** | A lapsed deadline adjudicates unattended and a pre-expiry warning sends |

## Why this order

- **The unmeasured assumptions are all in the store path.** [ADR 026](DECISIONS.md)'s ~90–110 MB is
  estimated, [ADR 027](DECISIONS.md) flags free-tier storage headroom and pause behavior as unverified,
  and typeahead is the only human-perceptible latency budget in the system now that it takes a database
  round trip. Step 1 is where a decision can still change.
- **The engine has no unknowns and floats.** Two numbered suites grade it against language-agnostic
  rules, so building it teaches nothing and invalidates nothing. It can go anywhere before step 4;
  moving it earlier costs sequencing efficiency, not correctness.
- **Hosting is smaller than its position in the log suggests.** A Node container moves between hosts for
  the cost of a Dockerfile. The **Supabase region** is the load-bearing half — [ADR 026](DECISIONS.md)
  makes same-region binding and a region move is a migration. Choose it in step 1.

## Sequencing constraints

Each of these costs rework if taken out of order.

1. **Step 0 precedes step 1.** `v1` drops sitelink counts at `Edge` and omits them from `entities`;
   [ADR 020](DECISIONS.md) makes ranking by them non-optional and asks for an actor disambiguator in the
   same bump. Building the entities table against `v1` means rebuilding it. The change is `transform` +
   `emit` against the cached raw partitions — no re-extract. Issue #19's fixes need a full re-extract
   and are measured at 0.02%; they do **not** go in this bump.
2. **Step 4 emits notification events even though nothing consumes them until step 6.**
   [ADR 018](DECISIONS.md)'s seam #2 is named the one item genuinely expensive to retrofit, and
   [ADR 029](DECISIONS.md) made it load-bearing.
3. **The case-fold library is chosen in step 1**, before corpus keys are written. Corpus and query fold
   identically or they never meet; `toLowerCase` is not case folding
   ([ADR 025](DECISIONS.md), [ADR 026](DECISIONS.md)).

## Not in this sequence

| Excluded | Source |
|---|---|
| Client-side typeahead index | [ADR 020](DECISIONS.md) — deferred behind the `suggest()` seam, trigger is playtest evidence |
| Web push | [ADR 029](DECISIONS.md) — opt-in upgrade, not built for v1 |
| Live play with a running clock | [ADR 018](DECISIONS.md) — deferred non-functional requirement |
| Cast-cap rescue | [ADR 019](DECISIONS.md) — measured and rejected, not skipped |
| Open matchmaking pools, solo mode, app-store deployment | [ADR 012](DECISIONS.md), [ADR 023](DECISIONS.md) |

## Open

- **Supabase free-tier terms.** Pausing on inactivity and storage headroom are both cost inputs to
  hosting and are answered by step 1's measurements. Verify current terms rather than a recorded figure.
- **Step 5's playtest is the only source of evidence** for the two revisit triggers already written into
  ADRs 019 and 020. Nothing before it produces that evidence.
