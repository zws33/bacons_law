# Agents Guide — Bacon's Law

A trivia game based on "Six Degrees of Kevin Bacon." **Two or more players on separate devices** take
turns naming movies and actors to build a chain of connections; each answer must connect factually to
the previous one. Play is **correspondence** — async, move-when-you-can, notified on your turn — with a
per-turn deadline. That is the only mode; live play with a running chess clock is deferred, and
**real-time is a time control, not an architecture** ([ADR 018](docs/DECISIONS.md)). A server owns
authoritative game state and validates every move against a **precomputed actor↔movie graph** held in
memory (O(1) set membership — no per-turn external API call).

A **round** ends when a player can't name a valid connection — that player is the round's loser. A
**match** is a series of rounds in which players accumulate strikes, lowest score best; how a strike
limit resolves (elimination, match end, or an open-ended series) is a per-mode configuration chosen
before play. Multiplayer is a day-one requirement, not a later extension.

> **`etl/` is the only durable source code and the only fixed contract.** It is a working pipeline
> that builds the graph the game engine validates moves against. Everything else in this repo —
> `:core`, `:backend`, `:app`, and the application/server design in `docs/DECISIONS.md` — is
> **provisional**: the entire application build-out will be reevaluated in a planning session,
> stack included. Treat nothing outside `etl/` as a fixed contract, and never preserve a signature,
> module layout, or design decision merely because it is already in the tree.
>
> **What that means for the docs.** `docs/DECISIONS.md` (ADRs 008–020) records the reasoning that got
> the project here — read it for *why*, not as commitments. Everything under
> [`docs/investigations/`](docs/investigations/) — including the system-design case study — is
> **non-normative by location**: records of how questions were investigated, containing falsified
> hypotheses by design. Never cite one as authority. There is currently **no roadmap document and no
> architecture-orientation skill**; both were retired pending regeneration after the planning session,
> so don't infer phase or status from any file.
>
> This file holds the **always-on operating rules**: repository layout, build/test commands,
> conventions, and the architecture boundaries below — which are tiered by what actually binds.
>
> **Prior efforts preserved as reference, not maintained** — do not modify unless explicitly asked: the
> Kotlin/Compose Android client (`:app`) and the Python/FastAPI showcase (branch
> `fullstack-py-ts-rewrite`, tag `python-fastapi-showcase`). Both were built on the per-turn TMDB call
> this architecture exists to remove; [docs/HISTORY.md](docs/HISTORY.md) records what they were and why
> they ended. Their detailed plans were deleted — do not go looking for them in the tree.

---

## Repository layout

The repo root is intentionally **stack-agnostic** — it holds shared docs and meta only. Each
implementation/component is a **self-contained project in its own top-level directory** with its own
toolchain. Adding a new (polyglot) experiment is *adding a directory*, not restructuring the root.

Gradle commands run from `kotlin/` (that's where `settings.gradle.kts` and the wrapper live). Gradle
module notation (`:core`, `:backend`, `:app`) is unchanged — it's relative to the `kotlin/` project.

### `:core` — the pure round engine (provisional)

The round state machine: `GameState`, `Move` (`Move.Actor` / `Move.Movie`), `playMove`, `forfeit`. It
has no platform or I/O dependencies and **must stay that way** — that property is the requirement, not
this particular implementation of it.

It builds **one chain** and reports who failed. Strikes, elimination, match end, and standings are the
match layer's, which does not exist yet. `GameState` is misnamed for this reason: it is round state.

The engine checks set membership (`castIds.contains(...)`) and makes no network calls. **The identifiers
are Wikidata QID strings** (`"Q23844"`) — that's what the graph artifact emits and what any engine must
consume. The current Kotlin code still declares `id: Int` and `castIds: Set<Int>`, a leftover from the
dropped TMDB data source ([ADR 010](docs/DECISIONS.md)); it does not match the data and carries no
authority. Reconcile it whenever the engine is next touched.

Note what that costs: `:backend` and `:app` both declare `implementation(project(":core"))`, and
eight files across them consume `Move` and `GameState` directly. Retyping the IDs breaks the Gradle
build, so the reconciliation includes updating those call sites — that is not "modifying" `:app` in
the preserved-as-reference sense above; it is keeping `kotlin/` compiling.

**The engine spec is [docs/ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md)** — rules R1–R15 plus a
numbered conformance suite, language- and framework-agnostic. Read it before changing engine behavior,
and satisfy it in whatever the engine is rewritten as. It is authoritative over
`kotlin/core/src/commonMain/kotlin/me/zwsmith/core/GameEngine.kt` and its tests, which are prototype
code: the spec records where they diverge from it (reporting a winner instead of a loser, the `Int`
IDs, absent construction validation, and repeat tests whose fixtures don't isolate the repeat rule).
The `movie-actor-chain-game` skill covers the domain rules and vocabulary, but is deliberately
implementation-agnostic and leaves repeats, the opening move, and "appeared in" policy open; the
answers this project has taken to those are in the **Architecture Boundaries** section below and
pinned as test cases in the conformance spec.

### `:backend` — the server (provisional)

Still the thin TMDB proxy it started as (movie/person search, credits). The graph-backed authoritative
session server has not been built; whether it is built here, in Kotlin, at all, is open. It depends on
`:core`, never the reverse. For the session-layer design as currently reasoned (durable store,
transport-agnostic move pipeline, identity, and the correspondence build order), see
[ADR 012](docs/DECISIONS.md) and [ADR 013](docs/DECISIONS.md) — both as amended by
[ADR 018](docs/DECISIONS.md), which drops the WebSocket transport and the real-time mode. Move
submission is request/response; there are no sockets to build.

### `etl/` — the offline graph build (Python) — **the durable part**

A separate Python toolchain (`uv`/`ruff`) that runs offline, never in the request path. It produces
the versioned graph artifact everything else is written against, and it works today. This is the one
component not up for reevaluation; Python is the right tool for the data-wrangling, and the polyglot
split is allowed across the offline/online seam only (see ADR 011). Its own operating rules are in
[etl/AGENTS.md](etl/AGENTS.md).

### `:app` — Android client (reference only)

Compose UI built for the old pass-the-phone, TMDB-backed model. It depends on `:core` and never holds
data-source credentials. It is not maintained, and the eventual client — Android, web, or otherwise —
is a planning-session question.

---

## Environment Setup

**There is no TMDB key in the new architecture** — validation data comes from CC0 Wikidata, built
offline. Do not reintroduce a per-turn movie-API dependency.

- **ETL:** runs offline; its Wikidata access needs no secret. Output is a versioned graph artifact
  consumed by the server.
- **Server:** its storage dependencies are **undecided** — the durable store and the presence/broadcast
  mechanism are planning-session questions, so there are no environment variables to document yet.
  Whatever is chosen, inject credentials from the environment; never commit them.

---

## Build & Test Commands

Gradle commands run from `kotlin/`; the ETL runs from `etl/`. No build tooling runs from the repo root.

`./gradlew :core:jvmTest` is the fast feedback loop for game logic. Note the target: `:core` is a
KMP module (`commonMain` / `jvmTest`), so there is **no `:core:test` task**; `allTests` runs every
target.

---

## Deployment

**There is no single-instance constraint.** Earlier revisions of this file said the server must run as
one long-lived instance because persistent WebSockets and the in-process graph ruled out scale-to-zero
and multi-instance autoscaling. [ADR 018](docs/DECISIONS.md) dropped the sockets, and the graph half of
that claim was never true: the artifact is ~21 MB, read-only, and identical everywhere, so N instances
each load a copy and coordinate nothing. **Do not reintroduce that constraint**, and do not cite the
in-process graph as an argument about instance count.

What survives is a **cold-start** consideration — the artifact is loaded at boot, so scale-to-zero
costs whatever that load takes. That is a measurement, not a ruling, and turns are minutes-to-days
apart. **Hosting is an open planning-session question**, Fly.io included; nothing in the architecture
picks a vendor.

Concurrent writes are serialized by **optimistic concurrency (version/CAS) on the durable store**. Note
what this is *for*: by the rules, two players cannot contend for the same turn. The real writers are
**duplicate submissions** (a slow request plus a re-tap or client retry — one player racing themselves,
which the turn rule does not prevent), **deadline adjudication** (not a player, and it can fire while
that player submits), and **match-level quits** (not turn-scoped). This needs a version column and a
`WHERE version = ?`, not coordination infrastructure — no distributed lock, no external coordinator, no
in-process `Mutex`. **The durable store is undecided** — see [ADR 012](docs/DECISIONS.md). There is no
presence/broadcast mechanism to decide.

---

## Code Conventions

- **Commits:** Conventional commit format — `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- **Kotlin style:** follow existing style; prefer pure functions and immutable data in `:core`.
- **Build versions:** declared in `gradle/libs.versions.toml`. Don't hardcode version strings.
- **Python (etl/):** keep it self-contained and offline.

---

## Architecture Boundaries

### Binding — these follow from the ETL contract

They hold across any rewrite, in any language. They are the reason `etl/` exists; discarding one
discards the point of the pipeline.

**Validation data is precomputed offline.** The actor↔movie relationship is built by the ETL into a
versioned artifact and loaded read-only at boot. **Do not add a per-turn external API call** to the
move path — that is the anti-pattern this architecture exists to remove. A consequence worth stating
outright: **graph membership defines validity**, not real-world truth — an edge the artifact does
not carry is not a legal move, however true it is off-graph.

**Validation is co-located with the graph, in-process.** The O(1) check holds **only** while the graph
and the validation logic share a process. **The engine/data seam must never cross a network hop** — do
not split the engine and the graph across services (CASE_STUDY §2/§6, ADR 009).

**Cast IDs are the validation contract, and they are Wikidata QID strings** (`"Q23844"`). A movie move
carries the set of cast member QIDs, populated from the in-memory graph before the move reaches the
engine. This keying is fixed by the graph artifact — a property of the data, not of whatever engine
reads it. (The Kotlin `:core` still says `Set<Int>` from the TMDB era; the data wins.) **Never pre-map
QIDs to integers in the ETL** — if some engine wants a different ID type, that belongs in its loader.

**Movies only, no TMDB.** The source is CC0 Wikidata, built offline; documentaries and TV films are
excluded at extract. There is no API key anywhere in this project.

**Keep the engine pure.** No platform dependencies, no I/O, no network — so it is testable without
mocks and shareable across server and clients. This is a property to preserve, not a statement about
`:core` specifically. New game logic goes in the engine with a test.

### Current decisions — provisional, subject to reevaluation

These are where the design stands per ADRs 008–020. They are reasoned positions, not commitments;
the planning session may replace any of them. Follow them absent a decision to the contrary, but
don't defend them as invariants. **ADR 020 is the exception** — it is a planning-session output
rather than an input to one, and it names its own revisit trigger (playtest evidence that typeahead
latency is felt).

**The game is turn-based. Real-time is a time control, not an architecture** (ADR 018). Correspondence
is the primary and only mode built. Live play with a running chess clock is **deferred, not designed
for** — it is a non-functional requirement noted for later, and the cost of that deferral is three
seams (below), not a mode. Do not add a persistent-socket transport, a presence service, or a broadcast
channel; do not evaluate stacks on connection-holding, idle-socket memory, or broadcast fan-out. The
game rewards recall and strategy, not reaction time, so the budget for delivering an opponent's move is
seconds.

**Opponents learn of a move by polling + push.** Adaptive polling (~2s while the game view is
foregrounded and it is not your turn; stopped when backgrounded), plus push notification to the
device-anchored token (ADR 013). The player who moved sees the result in their own response. This is
stateless — any instance can serve it.

**Store a deadline, not a mode.** A turn deadline is `turn_duration` plus a `deadline_at` timestamp; a
60-second turn and a 3-day turn are the same field at different values. **Do not introduce a
`realtime | correspondence` enum** — a mode enum branching through the codebase is how one system
becomes two. This replaces ADR 012 §2.

**Three seams keep live play cheap to add later.** They are the entire cost of deferring rather than
dropping it: (1) the move core stays transport-agnostic — `(player, gameId, validatedMove) -> result`
as a plain function, no HTTP types in domain logic; (2) **move handling emits a notification event
rather than calling the notifier** — "game X advanced to player B," consumed by a delivery layer; this
is the one item genuinely expensive to retrofit; (3) the deadline is data, per above.

**Name resolution runs server-side; the client index is deferred behind a seam** (ADR 020). Typeahead
resolves against the in-memory `entities` map over request/response, with the client debouncing input.
Shipping the index to the client — ~1.6 MB gzipped — is **deferred, not rejected**; the trigger to
build it is playtest evidence that the latency is felt, not a threshold set in advance. The entire cost
of that deferral is one seam, a fourth of the kind listed above: **the client's suggestion call is an
interface — `suggest(prefix) -> Candidate[]` — never a `fetch` inlined into an input handler.** The
server keeps the resolve endpoint either way, because it must re-resolve any submitted QID regardless:
a client's claim that a QID exists and is of the type it says is not trustworthy.

**The typeahead searches the whole corpus, never the legal moves.** Scoping suggestions to the previous
entity's neighbours (~15 actors per film, ~5 films per actor) would be trivially fast and would hand
the player the answer. The game tests recall — a typeahead that only suggests valid moves is not a
faster typeahead, it is a different game. This is why name resolution is a 136,689-record search
problem and not a 15-record one.

**Search keys are derived at boot, never in the ETL.** The artifact emits the neutral contract; folded
search keys — Unicode case folding (*not* `toLowerCase`), NFD with combining marks stripped,
punctuation normalised, indexed at every word start so `matrix` finds *The Matrix* — are a consumer
concern exactly as ID adaptation is (ADR 016). Deriving them loader-side also means the index shape can
change without a graph rebuild. Results are ranked by sitelink count, which `entities` does not yet
carry; surfacing it is a `transform`+`emit` change, not a re-extract.

**A durable store is authoritative for game state — which store is undecided.** The serialized
`GameState` (plus players, turn-duration/deadline, and per-player time state) is persisted per game. The
requirements it must meet: survive restarts, span days for correspondence play, hold serializable
state, and support compare-and-swap on a version so concurrent writes serialize (ADR 012). **No
authoritative state behind a TTL** — that was the concrete failure of the earlier design, and it is the
one thing here that generalizes past any particular product.

**Concurrency control is a version column, not infrastructure.** Two *players* cannot contend for the
same turn — that is a rule. CAS exists for three other writers: duplicate submissions (one player
racing themselves via re-tap or client retry, which the turn rule does not prevent), deadline
adjudication, and match-level quits. A client-generated move ID for idempotency is recommended: CAS
rejects a duplicate, surfacing an error for something that actually succeeded, whereas an idempotency
key returns the original result. **Horizontal scaling is neither paired nor blocked** — ADR 008's
"coordinated locking *and* a broadcast channel" is void, the broadcast half being an artifact of
holding sockets and the locking half being CAS.

> Specific products were named in ADRs 008–012 and have been **deliberately removed from this file** so
> that a fresh planning pass evaluates storage and persistence on the requirements above rather than
> inheriting an answer. Do not reintroduce a named store here until that session picks one.

**Round and match are separate layers.** The **round engine** builds one chain: opening move, turn
rotation among N players, per-move validation, and — on an invalid move or a give-up — a round result
naming the player who failed. That is its entire job, and it is specified in
[docs/ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md). The **match layer** owns everything after:
strike accounting, whether a strike limit eliminates a player or ends the match, standings across an
ongoing series, mode configuration, and who opens the next round. How a failure is punished is
configurable per mode and must not leak into how a turn is evaluated. The match layer is unspecified —
writing it is a planning-session output.

**The three questions `movie-actor-chain-game` leaves open, answered.** The domain skill is
deliberately implementation-agnostic about repeats, the opening move, and "appeared in" policy;
these are the answers this project has taken.

**Repeat detection is on.** Within a round the same move may never appear twice: reusing an actor or
movie already in the chain is rejected — a game rule, not a bug. Uniqueness is per type: an actor and
a movie may share an ID without colliding.

**Across rounds, reuse is allowed by default, and configurable.** A fresh round makes every entity
available again. A settings-level hard mode may forbid reuse for a whole match; the round engine
supports it by accepting `excludedActorIds` / `excludedMovieIds` at round setup, which the match layer
seeds and which default to empty. The engine does not know which mode is in play. Note that these
exclusions bind the opening move too — otherwise every round could open on a banned entity
([docs/ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md) R1/R5).

**The opening move is not connection-checked.** On an empty chain `playMove` skips the connection and
type checks — there is no predecessor — so either an actor or a movie may open. "The first move must
be an actor" is a caller concern (UI / session layer), not an engine rule. The repeat check still
runs; on an empty chain with no exclusions it cannot fail, which is why the opener looks
unconditional in the default mode (see the paragraph above).

**Multiplayer (N > 2) is a day-one shipping requirement.** The two-player prototype is not the target.
At the round layer this costs almost nothing — rotation is modulo `playerCount`, and the round reports
the index of the player who failed. What a failure *costs* is a match-layer question (below).

**The round engine names a loser, never a winner.** Every round has one unambiguous loser: the player
on turn when the chain broke. It has no natural winner — a player who did not fail is simply not the
loser, and crowning whoever played the last valid move is an arbitrary convention. If a mode wants
that, the match layer derives it. See [docs/ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md) R8/S3.
The prototype's `GameOver.winnerIndex` is the two-player convention generalized by modular arithmetic
and is wrong above two players; treat it as a leftover on par with the `Int` IDs.

**"Appeared in" means "in the capped graph."** Cast comes from truthy `wdt:P161`, so voice, cameo,
and uncredited roles count exactly insofar as Wikidata records them. The sharp edge is the cap: each
film keeps only its top-N cast ranked by the actor's own sitelink count (`cast_cap`; billing order
`P1545` is ~8% populated and unusable — [etl/AGENTS.md](etl/AGENTS.md)). **A real but obscure cast
member is absent from the graph and is therefore not a valid move.** Expect "but they were in it!"
in playtests; that is a dial (`cast_cap`, `min_cast`), not a bug.

---

## What to Avoid

The boundaries above restated as failure modes — these are the mistakes this architecture exists to
prevent, and the Python showcase made the first one. Both tiers are represented: bypassing repeat
detection and the out-of-scope list are Current decisions, not Binding.

- **A per-turn movie-API call in the move path.** Validation is precomputed offline and served
  in-process. This was the showcase's mistake and the reason for the pivot.
- **Splitting the engine from the graph across a network boundary.** Co-location is load-bearing.
- **I/O in the engine** — no network, no database or cache calls, no platform deps.
- **A persistent-socket transport, a presence service, or a broadcast channel.** The game is
  turn-based and rewards recall, not reaction time; moves go over request/response and opponents learn
  of them by polling + push ([ADR 018](docs/DECISIONS.md)). Related: **do not evaluate stacks on
  connection-holding, idle-socket memory, or broadcast fan-out** — that framing in
  [docs/CASE_STUDY.md](docs/investigations/000-system-design-case-study.md) §5–§6 is superseded, and inheriting it silently picks a
  stack for a workload this system does not have.
- **Asserting a single-instance constraint**, or citing the in-process graph as an argument about
  instance count. The graph is read-only and identical on every instance. Cold start is the only live
  consideration, and it is a measurement.
- **A `realtime | correspondence` mode enum.** Store `turn_duration` + `deadline_at`; the modes differ
  only in the number.
- **Citing anything under [`docs/investigations/`](docs/investigations/) as authority.** Those are
  **records, never rules** — they contain falsified hypotheses and revised framings by design. If an
  investigation produced a binding outcome, that outcome was promoted into an ADR, this file, or a
  spec; cite *that*. A claim found there is evidence of what someone once thought, not of what the
  project has decided.
- **TMDB as a runtime dependency**, or any API key. The source is CC0 Wikidata, built offline.
- **Pre-mapping QIDs to integers in the ETL.** ID adaptation is a loader-side concern.
- **Deriving folded search keys — or any search-optimized index — in the ETL.** The same rule as the
  line above, for the same reason: the artifact emits the neutral contract, and search shape is a
  consumer concern derived at boot ([ADR 020](docs/DECISIONS.md)). It is also what keeps the index
  format changeable without a graph rebuild.
- **Scoping the typeahead to the legal moves.** Suggesting only the previous entity's neighbours is the
  obvious "helpful" optimization, and it hands the player the answer. The typeahead searches all
  136,689 entities precisely so that it discloses the answer *space* and never an answer.
- **Inlining the suggest call into an input handler.** `suggest(prefix) -> Candidate[]` is an
  interface, and it is the only thing keeping the client-side index a cheap follow-up rather than a
  rewrite ([ADR 020](docs/DECISIONS.md)).
- **Bypassing repeat detection.** It is a game rule.
- **Out-of-scope mechanics.** Not to be introduced unasked: pass/skip, challenge or dispute flow,
  difficulty settings and obscurity filters, single-player/quiz-master mode, open matchmaking pools,
  and credentialed accounts (email/OAuth, cross-device, recovery — [ADR 013](docs/DECISIONS.md)).
  **Now in scope:** time controls and durable game-state persistence and persistent identity
  ([ADR 012](docs/DECISIONS.md)); **multiplayer at N > 2**; and **strike-based scoring at the match
  layer** — accumulating strikes across rounds, ranked lowest-first, with an optional strike limit
  that eliminates a player or ends the match. Scoring was formerly out of scope; it is now the match
  layer's purpose. Within a round there is still no miss tolerance: the first failure ends the round.
- **Scoring, strikes, or elimination inside the round engine.** They belong to the match layer, and
  which one a mode uses is player-configurable before the match starts.
- **A winner field on the round result.** The round names a loser; any winner convention is a
  match-layer overlay ([docs/ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md) S3).
- **Assuming two players.** Multiplayer ships day one; `playerCount` has no upper bound at the engine.
- **TV shows and documentaries** — movies only.

---

## Key Documents

| Document | Purpose |
|----------|---------|
| [docs/DECISIONS.md](docs/DECISIONS.md) | ADR log — the reasoning that got the project here; 008–020 cover the current direction. **Read [ADR 018](docs/DECISIONS.md) first** — it amends 008, 011, and 012 on transport, hosting, and modes. Read for *why*, not as commitments. **[ADR 020](docs/DECISIONS.md) is the first planning-session output** and is settled, not provisional |
| [docs/investigations/](docs/investigations/) | **Records, never rules.** Investigation write-ups and design retrospectives, including hypotheses that were falsified. Non-normative *by location* — never cite one as authority for a change; binding outcomes are promoted out into ADRs, this file, or a spec. Read [its README](docs/investigations/README.md) before using anything inside |
| [docs/investigations/000-system-design-case-study.md](docs/investigations/000-system-design-case-study.md) | System-design reasoning behind this architecture (a retrospective, not a build spec). **§2, §5, and §6 are superseded by [ADR 018](docs/DECISIONS.md)** and carry inline markers — they assume a WebSocket transport this project no longer has |
| `movie-actor-chain-game` skill | Domain rules and vocabulary (implementation-agnostic; leaves project-specific rules open) |
| [docs/ENGINE_CONFORMANCE.md](docs/ENGINE_CONFORMANCE.md) | **The round-engine spec of record.** Rules R1–R15 + a numbered conformance suite; language-agnostic, generates a test suite in any stack. Defines the round/match seam |
| `kotlin/core/.../GameEngine.kt` + tests | Prototype implementation — subordinate to the conformance spec, which records where it diverges |
| [etl/AGENTS.md](etl/AGENTS.md) | ETL operating rules and the load-bearing facts of the graph build |
| [docs/HISTORY.md](docs/HISTORY.md) | The two prior efforts (Kotlin pass-the-phone MVP, Python/FastAPI showcase) — what they were, why they ended, where the code lives. Reference only; neither is guidance |
