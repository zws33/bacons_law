# Decision Log

Lightweight ADR-style record of key technical and product decisions.

> **001–007** are the original Kotlin/Android decisions, largely superseded. **008–013** established
> the current architecture — a server validating moves against a precomputed Wikidata graph built by a
> Python ETL. **014–017** record decisions made since that were previously only in `AGENTS.md`: the
> round/match split, N-player multiplayer, the QID contract, and the conformance spec's authority.
> The archived Python/FastAPI showcase kept its own log; it was deleted along with that effort's plans
> — see [`HISTORY.md`](HISTORY.md).
>
> **Where an ADR has been overtaken, it says so inline at the top.** Read those markers before acting
> on an ADR's contents — several early ones remain useful for their reasoning while their concrete
> choices no longer hold.
>
> **Phase numbers below refer to a roadmap that has since been retired.** They are kept as part of the
> dated record — don't read them as current sequencing or infer status from them. These ADRs record
> the reasoning that got the project here, not commitments; see [`../AGENTS.md`](../AGENTS.md).

---

## 001: MVP is pass-the-phone two-player, not solo chain-building

> **Superseded by [ADR 008](#008-multi-device-server-authoritative-play-is-the-core-requirement).**
> Pass-the-phone was the single-device MVP; multi-device, server-authoritative play is now the core
> requirement.

**Date:** 2026-03-19

**Context:** The core fun of the game is being *quizzed* — prompted with a movie or actor and having to prove you know a connection. A solo chain-building mode where you browse and select freely lacks the reactive, unpredictable element that makes the game engaging.

**Decision:** MVP is a two-player, pass-the-phone game where the other player's choices create the unpredictability. The app validates moves, it doesn't generate prompts.

**Consequences:** Requires two people physically present to play. Single-player "quiz-master" mode (app as prompter) is a future enhancement, not the starting point.

---

## 002: Android/Kotlin/Compose for MVP client

**Date:** 2026-03-19

**Context:** Evaluated building the MVP as a Go backend + web frontend (for T-shape learning) vs. an Android app (fastest to ship). The existing repo has Kotlin/Compose code and TMDB integration.

**Decision:** Ship the MVP as an Android app. A Kotlin/Ktor backend enters the picture first as a thin TMDB proxy (Phase 1), then evolves into a multiplayer game server (Phase 4).

**Rationale:** Pass-the-phone is inherently a mobile interaction. Android is the fastest path to a playable game. The backend is introduced early to avoid shipping TMDB credentials in the APK, not for multiplayer — but it's designed to grow into the multiplayer layer rather than being thrown away.

**Consequences:** The project stays all-Kotlin across client and server. `:core` is the shared domain layer — both `:app` and `:backend` depend on it.

---

## 003: Strip MVP game mechanics to the core quiz loop

> **Partially superseded.** The principle — ship the core loop, add mechanics from real play — still
> holds, and there is still **no miss tolerance inside a round**: the first failure ends it. But two
> items on the out-of-scope list have since moved *in* scope. **Time controls** are a first-class
> requirement ([ADR 012](#012-async-correspondence-is-a-first-class-mode-durable-store-authoritative)),
> and **strike-based scoring with optional elimination** is the match layer's entire purpose
> ([ADR 014](#014-round-and-match-are-separate-layers-the-round-engine-names-a-loser)). Passes,
> challenges, table vetoes, and obscurity sliders remain out of scope.

**Date:** 2026-03-19

**Context:** A prior brainstorming plan proposed passes, challenges, miss tolerance, time limits, elimination/continuous scoring modes, table vetoes, and obscurity sliders — all before shipping.

**Decision:** MVP has none of these. The game loop is: select a connection, app validates, pass the phone. First invalid move loses. That's it.

**Rationale:** Every mechanic added before shipping is a mechanic you're guessing players want. Ship the core loop, play 10 rounds, then add what's actually missing based on real experience.

**Consequences:** The game may feel thin at first. That's acceptable — it's faster to add mechanics to a shipped game than to balance them in a vacuum.

---

## 004: Existing codebase is a starting point, not sacred

**Date:** 2026-03-19

**Context:** The existing repo has a Kotlin game engine (`:core`), Compose UI with TMDB search, and a multi-module architecture. The game engine models two-player alternation with move validation. The UI has search but isn't connected to the game logic.

**Decision:** Use the existing code as a starting point — especially the TMDB integration and project structure — but rewrite or restructure freely where it doesn't serve the MVP.

**Rationale:** The existing code amounts to a few days of work. Preserving it for sunk-cost reasons would constrain design decisions. The TMDB API integration and Retrofit setup are genuinely reusable; the game state machine may need reworking to match the refined spec.

**Consequences:** Need to evaluate the existing `:core` game engine against the game spec. It may map cleanly, or it may be simpler to rewrite with the spec as the guide.

---

## 005: Kotlin/Ktor backend proxy for TMDB — credentials never in client binaries

> **Partially superseded.** The TMDB-proxy role is dropped by
> [ADR 010](#010-wikidata-cc0-is-the-data-source-tmdb-is-dropped) (data now comes from Wikidata,
> precomputed offline), and the Cloud Run hosting choice is replaced by
> [ADR 011](#011-kotlinktor-server--python-etl-single-flyio-instance-not-cloud-run). The
> "credentials never in a client binary" principle still holds — trivially, since there are now no
> credentials.

**Date:** 2026-04-01

**Context:** The Android app needs TMDB API access for movie search, person search, and credits. The straightforward approach is to inject the key as a `BuildConfig` field in the APK. However, Android APK binaries are extractable — "not committed to source control" is not the same as "not recoverable from the binary." Any key shipped in a client binary should be treated as public.

The project also has a long-term goal of remote multiplayer. A backend is inevitable; the question is when to introduce it.

**Options considered:**
1. Ship Phase 1 with direct TMDB calls from the app. Add a backend later when multiplayer requires it.
2. Introduce a minimal Ktor backend proxy now. App calls proxy; proxy calls TMDB with the secret.

**Decision:** Option 2. A thin Kotlin/Ktor service deployed on Cloud Run, with the TMDB API key stored in Google Secret Manager. The Android app calls backend-owned endpoints for all TMDB data.

**Rationale:** The proxy is trivial to stand up, and the cost of doing it now is low relative to the benefit. More importantly, the backend built for credential security is the same backend that will eventually own multiplayer game state — it's not throwaway work. The TMDB domain layer built inside it (normalization, validation) becomes reusable when Phase 4 moves validation server-side. `:core` being pure Kotlin/JVM means both `:app` and `:backend` share the same domain types without duplication.

**Consequences:**
- TMDB credentials are never embedded in any client binary. This invariant must hold for all future clients (iOS, web).
- Phase 1 scope expands to include standing up the backend before wiring the TMDB data layer in `:app`.
- The project is all-Kotlin across client, server, and shared domain. No Go.
- Cloud Run scales to zero when idle — infrastructure cost is effectively zero at hobby scale.

---

## 006: Ktor Client + kotlinx.serialization for all client network layers

**Date:** 2026-04-02

**Context:** The `:app` module currently uses Retrofit + Gson for HTTP. Phase 5 plans to share the network layer with an iOS client via Kotlin Multiplatform. Retrofit is JVM/Android-only; migrating it during Phase 5 would require a full rewrite of the data layer at a time when the codebase is larger and more coupled.

**Decision:** When rewriting the `:app` data layer in Phase 1 (Task 3), use Ktor Client + kotlinx.serialization instead of Retrofit + Gson. Retrofit is removed entirely at that point.

**Rationale:** Ktor Client is KMP-compatible today. The `:app` data layer rewrite is already planned work — the incremental cost of choosing Ktor Client over Retrofit at that moment is near zero, while the future cost of not doing so is a full rewrite. The `:backend` module also uses Ktor Server + kotlinx.serialization, so this keeps the serialization library consistent across the stack.

**Consequences:**
- Retrofit and Gson are removed from the project when Task 3 lands.
- The `:app` network layer can move to a `:shared` KMP module in Phase 5 with minimal changes.
- All future clients (iOS, web) should use Ktor Client + kotlinx.serialization for the same reason.

---

## 007: GameViewModel owns game state for Phase 1; client thins in Phase 4

**Date:** 2026-04-03

**Context:** A clean architecture for this app would have a `GameRepository` owning game state, a `MediaRepository` abstracting data sources, and a use case layer orchestrating between them. However, this structure has no second implementation or second caller in Phase 1 — it would be abstraction without a job.

**Decision:** For Phase 1, `GameViewModel` directly owns `GameState`, calls `GameEngine` for transitions, and calls `Repository` for data. The `Repository` is a pass-through to the data layer (search and credits fetch). No interactor or use case layer.

**Rationale:** Game state is ephemeral and local in Phase 1 — a ViewModel is the right scope. Introducing `GameRepository` and a use case layer before there is a second data source, a second caller, or persistence requirements is premature abstraction. The right time to add these layers is when they have a concrete job.

**Consequences:**
- In Phase 4 (remote multiplayer), this inverts: `:backend` becomes the authoritative game state owner, and `:app` becomes a thin state consumer. The ViewModel will shrink significantly — it will render state received from the server rather than state it owns.
- `:core` remains the shared domain layer throughout. `GameState`, `Move`, and `Player` are valid on both client and server.
- When Phase 4 arrives, introduce `GameRepository` (wrapping the WebSocket/SSE connection) and a use case layer at that point — not before.

---

## 008: Multi-device, server-authoritative play is the core requirement

> **Amended.** The core decision holds. The concurrency mechanism below does not: the in-process
> per-room `Mutex` is demoted by
> [ADR 012](#012-async-correspondence-is-a-first-class-mode-durable-store-authoritative) §4 in favour
> of optimistic concurrency (version/CAS) on the durable store. Read "this is the v1 design" as
> historical. The two-player framing is superseded by
> [ADR 015](#015-multiplayer-beyond-two-players-is-a-day-one-requirement).

**Date:** 2026-06-29

**Supersedes:** [ADR 001](#001-mvp-is-pass-the-phone-two-player-not-solo-chain-building) (pass-the-phone was the single-device MVP, not the end state). Carries forward the substance of the Python showcase's ADR 009, re-expressed for the Kotlin trunk.

**Context:** Multiple devices connect to the same room over the network, and the backend owns authoritative game state. The single-device framing misleads design — most concretely, it makes the room store's concurrency model look like a non-problem ("turns are sequential, only one device") when two devices can send near-simultaneous messages to the same room.

**Decision:** Multi-device play is core, not a deferred enhancement. The Ktor server is the authoritative owner of game state; clients submit move *intents* over a WebSocket and render the state the server pushes back. Turns remain sequential as a game rule, but turn-validation and state-mutation are atomic *together* on the server — sequential turns are a rule the server enforces, not a guarantee that only one message arrives at a time.

**Consequences:**
- **Multi-device (clients) ≠ multi-instance (servers).** A single instance can hold thousands of WebSocket connections across thousands of rooms; multi-device does **not** by itself require horizontal scaling.
- **Single instance + per-room lock (Kotlin `Mutex`) is sufficient.** Concurrent moves to the same room are serialized by an in-process per-room lock. This is the v1 design.
- **Horizontal scaling is deferred and comes as a pair:** externally coordinated locking *and* a broadcast channel between instances (a second instance can't see the first's sockets). Build both or neither.
- This realizes the inversion anticipated in [ADR 007](#007-gameviewmodel-owns-game-state-for-phase-1-client-thins-in-phase-4): the server becomes the authoritative owner; `:app` thins to a state consumer.

---

## 009: Validation is precomputed offline and served in-process — no per-turn external API

**Date:** 2026-06-29

**Context:** The intuitive approach validates "did this actor appear in this movie?" with a movie-API call per turn — the Python showcase did exactly that (a TMDB credits call per movie move). [CASE_STUDY.md](CASE_STUDY.md) (§2–3) shows this is backwards: precompute the actor↔movie relationship once, offline, and the per-turn check collapses to an O(1) set-membership lookup. The system is connection-bound, not compute-bound; the connection check is the cheapest thing in it.

**Decision:** The actor↔movie relationship is precomputed offline into a bipartite graph (`movie_id → set(actor_id)`, `actor_id → set(movie_id)` — generic notation predating the source choice; the keys are Wikidata QID strings, see [ADR 016](#016-cast-ids-are-wikidata-qid-strings-id-adaptation-is-loader-side)) and loaded **read-only, in-process** into the server at boot. Move validation is `castIds.contains(...)` against the loaded graph — no network call in the hot path. The pure `:core` engine is unchanged; only its data source changes.

**Rationale & consequences:**
- The O(1) property holds **only while the graph lives in the same process as the validation logic** (CASE_STUDY §2/§6 caveat). The engine/data seam must not cross a network hop — this constrains deployment (the server loads the artifact at boot; see [ADR 011](#011-kotlinktor-server--python-etl-single-flyio-instance-not-cloud-run)).
- **Cast-depth cap (top-N billed)** is applied at build time — at once a gameplay knob, a policy lever for what "appeared in" means, and a graph-size lever (CASE_STUDY §3).
- **Name resolution moves to the boundary:** a typeahead resolves names to entity IDs before submission; the server receives `{type, id}`, never free text.

---

## 010: Wikidata (CC0) is the data source; TMDB is dropped

**Date:** 2026-06-29

**Supersedes the TMDB premise of:** [ADR 005](#005-kotlinktor-backend-proxy-for-tmdb--credentials-never-in-client-binaries) (the Ktor service is no longer a TMDB proxy).

**Context:** ADR 005 introduced a proxy to hide a TMDB key. With validation precomputed offline ([ADR 009](#009-validation-is-precomputed-offline-and-served-in-process--no-per-turn-external-api)), the data source is a build-time input, not a request-path dependency. CASE_STUDY §4 separates copyright (facts aren't copyrightable — *Feist*) from contract (provider terms bind by *how you obtained* the data). TMDB's terms treat donation-funded operation as commercial and include an AI/ML clause — a recurring question for a no-profit hobby project.

**Decision:** Build the graph from **Wikidata (CC0)**. No attribution requirement, no AI restriction, no commercial-use question. The TMDB proxy is removed; there is no TMDB key anywhere in the new architecture.

**Consequences:**
- Provenance is clean permanently — adding donations or AI components later does not reopen a licensing question (CASE_STUDY §4).
- The ADR 005 "no credentials in a client binary" invariant holds trivially: there are no credentials.
- TMDB image assets are out of scope. If poster art is wanted later, that's a separate, explicitly-scoped decision reintroducing TMDB terms for the image path only.

---

## 011: Kotlin/Ktor server + Python ETL; single Fly.io instance, not Cloud Run

> **The language choice is reopened.** The *offline/online split* (Python ETL, everything else online)
> and the *hosting* decision (single long-lived Fly.io instance, not scale-to-zero) both hold — they
> follow from the load-bearing property, not from Kotlin. But "server: Kotlin/Ktor," "reuse the pure
> `:core` engine as-is," and "the running system stays all-Kotlin" are **provisional**: the whole
> application build-out, stack included, is to be reevaluated in a planning session. See
> [`../AGENTS.md`](../AGENTS.md).

**Date:** 2026-06-29

**Supersedes the hosting choice of:** [ADR 005](#005-kotlinktor-backend-proxy-for-tmdb--credentials-never-in-client-binaries) (Cloud Run scale-to-zero is incompatible with persistent WebSockets).

**Context:** The server is connection-bound (CASE_STUDY §6). Kotlin is the strongest language on hand, with structured concurrency (coroutines / virtual threads) well-suited to many long-lived, mostly-idle connections, sealed classes that model the engine, and KMP reach for an Android client. The offline graph build is data-wrangling work where Python excels — and CASE_STUDY §6 blesses a polyglot split across the *offline/online* seam (but **not** across the engine/data seam).

**Decision:**
- **Server: Kotlin/Ktor.** Reuse the pure `:core` engine as-is; rebuild `:backend` from a TMDB proxy into the graph-backed authoritative session server (WS rooms, live session state, in-process graph). Modernize `:app` into a multi-device client later (secondary).
- **ETL: Python**, a separate offline toolchain (`etl/`) producing the versioned graph artifact.
- **Hosting: a single long-lived Fly.io instance**, not Cloud Run — persistent WebSocket connections and in-process session state + graph are incompatible with scale-to-zero / multi-instance autoscaling.

**Consequences:**
- The running system stays all-Kotlin (client + server + shared `:core`), preserving [ADR 002](#002-androidkotlincompose-for-mvp-client)'s all-Kotlin property; Python is offline-only.
- A cache/coordination layer holds live room state and is the coordination point if horizontal scaling is ever justified ([ADR 008](#008-multi-device-server-authoritative-play-is-the-core-requirement)). Which layer is undecided — see the note at the top of [ADR 012](#012-async-correspondence-is-a-first-class-mode-durable-store-authoritative).
- Egress is the dominant cost driver at scale (CASE_STUDY §5); a Cloudflare-front + cheap-origin posture is a future lever, not a v1 requirement.

---

## 012: Async ("correspondence") is a first-class mode; durable store authoritative

> **Storage products withdrawn.** This ADR originally named specific technologies for the durable store
> and the cache/presence layer. Those names have been **removed from this document deliberately**, so
> that a full replanning pass evaluates persistence against the requirements rather than inheriting an
> answer. `git log -p docs/DECISIONS.md` has the original text.
>
> **What survives is the requirement set**, and it is the durable part of this decision: authoritative
> state must be serializable, survive restarts, span days, support compare-and-swap on a version, and
> **never sit behind a TTL**. Any candidate is judged on those. Everything else below — the
> transport-agnostic pipeline, clocks as session-layer state, correspondence-first build order — is
> storage-agnostic and unaffected.

**Date:** 2026-07-06

**Amends [ADR 008](#008-multi-device-server-authoritative-play-is-the-core-requirement):** the in-process
per-room `Mutex` is demoted (below). **Supersedes** parts of the ROADMAP "out of scope" list — turn
timers and game-history persistence move *in scope*. **[ADR 011](#011-kotlinktor-server--python-etl-single-flyio-instance-not-cloud-run)
survives** — real-time still requires persistent WebSockets + in-process graph on a single Fly
instance. Identity is split into [ADR 013](#013-persistent-player-identity-device-anchored-first).

**Context:** The product target is the chess.com model: at game creation a player picks a **mode** —
*real-time* (live, with a chess clock) or *correspondence* (async, move-when-you-can, notified on your
turn). Async is a firm functional requirement, not a future enhancement. The design it replaced — live
room state held in a TTL-scoped cache as the source of truth — cannot express a game spanning days or a
player with many concurrent games.

The engine (`:core`) is already mode-agnostic — a turn-based state machine with no concept of wall-clock
time. The difference between modes lives entirely in the **session layer**: state lifetime, transport,
notification, and clocks.

**Decision:**

1. **A durable store is authoritative** for game state. Any cache layer is demoted from source-of-truth
   to **presence + broadcast + hot-game cache**; authoritative state never sits behind a TTL. Realizes
   case-study lock-in #4 ("serializable authoritative state"). *Which* store, and which cache, is
   deliberately left open — see the note at the top of this ADR.
2. **`mode` and time-control are per-game config**, set at creation. One game-creation surface extends
   the existing `POST /rooms` (room code = "challenge a friend by link"). Open matchmaking pools are out
   of scope for v1.
3. **The move-processing core is transport-agnostic:** a handler over `(player, gameId, validatedMove)`.
   HTTP (correspondence) and WebSocket (real-time) are thin adapters into the same pipeline:
   *authenticate → load game → validate against graph → persist → notify.*
4. **Serialization is via optimistic concurrency on the store** (version/rev column, compare-and-swap on
   move), replacing the in-process `Mutex` as the authoritative mechanism. Works for both modes and
   survives an eventual multi-instance move. The `Mutex` may remain only as a same-instance fast-path.
5. **Clocks are session-layer state, part of the durable serializable game state**, never in `:core`.
   Two models: correspondence = per-move deadline (timestamp, lazy/swept); real-time = a running chess
   clock (server-authoritative, keeps ticking through disconnects). Their only engine interaction is
   injecting a terminal "out of time → loss" outcome.
6. **Build order: correspondence-first**, then real-time as an additive layer (WS transport + presence +
   pub/sub + the clock subsystem) on the proven foundation.

**Consequences:**
- Phase 3 is reframed: not "TTL-cache session layer" but "durable store + the shared move pipeline,"
  built correspondence-first.
- Phases 1 (ETL) and 2 (engine + graph loading) are unchanged. This does not block current ETL work.
- New **Game** entity: id, mode, time-control, players, serialized `:core` `GameState`,
  clock/deadline state, status, timestamps. The `GameState` serializes *inside* the Game row.
  (Written as "two players" originally; corrected by
  [ADR 015](#015-multiplayer-beyond-two-players-is-a-day-one-requirement) — the player list is
  N-ary, and per-player clock state is per-player, not a pair.)
- The real-time chess clock is a genuine subsystem, budgeted as such — not a per-turn timeout checkbox.
- Real-time gracefully degrading to correspondence on disconnect becomes nearly free (no live socket →
  deliver via push), if the notify abstraction is pluggable from the start.

---

## 013: Persistent player identity, device-anchored first

**Date:** 2026-07-06

**Supersedes** the "room-scoped opaque tokens, no accounts" strategy.
**Depends on [ADR 012](#012-async-correspondence-is-a-first-class-mode-durable-store-authoritative)**
(correspondence requires identity outliving a single game).

**Context:** Correspondence games span days, a player holds many concurrent games, and "it's your turn"
must reach a disconnected player. Each requires identity that outlives a room — room-scoped ephemeral
tokens can't express any of it. The open question is *how far* toward full accounts v1 goes.

**Options considered:**
1. **Full accounts** (email/login, cross-device, recovery) up front — matches chess.com, but builds an
   auth system before the game is playable.
2. **Device-anchored persistent tokens** — a durable token stored on-device, registered as a push
   target; upgradeable to a credentialed account later.

**Decision:** Option 2. v1 identity is a **device-anchored persistent token**: it establishes a stable
Player, carries push tokens, and backs the "my games" list — without a login system. A credentialed
account upgrade path (email/OAuth, cross-device, recovery) is designed for but deferred until
cross-device play or account recovery is actually needed.

**Consequences:**
- New **Player** entity: id, display name, push token(s), device anchor, (later) auth credentials.
- **Accepted v1 limitations:** a lost/wiped device loses that player's games, and a player can't play
  the same identity on two devices. Both are resolved by the deferred account upgrade — surface them in
  the UI ("add an email to save your games across devices") rather than hiding them.
- Enables a "my games" inbox and push-on-your-turn without an auth build.
- The upgrade must be non-destructive: claiming an account adopts the device-anchored Player's existing
  games, not a fresh identity.

---

## 014: Round and match are separate layers; the round engine names a loser

**Date:** 2026-08-05

**Partially supersedes [ADR 003](#003-strip-mvp-game-mechanics-to-the-core-quiz-loop):** scoring and
elimination were struck from scope entirely; they return as the match layer's purpose.

**Context:** The engine builds **one chain** and reports who failed. The product wants a *series* of
rounds with accumulating strikes, and different modes want to punish a failure differently —
elimination at a strike limit, match end, or an open-ended series. Putting any of that inside the
engine means how a failure is *punished* leaks into how a turn is *evaluated*, and every mode change
becomes an engine change.

**Decision:** Two layers with a hard seam.

- The **round engine** owns: the opening move, turn rotation among N players, per-move validation, and
  — on an invalid move or a give-up — a round result naming the player who failed. That is its entire
  job. Specified by [ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md).
- The **match layer** owns: strike accounting, whether a strike limit eliminates a player or ends the
  match, standings across a series, mode configuration, and who opens the next round.

The round result names a **loser, never a winner.**

**Rationale:** Every round has exactly one unambiguous loser — the player on turn when the chain broke.
It has no natural winner. A player who did not fail is simply not the loser, and crowning whoever
played the last valid move is an arbitrary convention that happens to read sensibly at two players and
is meaningless above that. If a mode wants a winner, the match layer derives one.

**Consequences:**
- **No scoring, strikes, or elimination inside the round engine**, and **no winner field** on the round
  result ([ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md) R8/S3).
- Within a round there is still **no miss tolerance** — the first failure ends it. ADR 003's principle
  survives at the round level; strikes accumulate at the match level.
- The **match layer is unspecified** and writing it is a planning-session output.
  [ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md) §Scope defines the seam it must attach to.
- The prototype's `GameOver.winnerIndex` is the two-player convention generalized by modular
  arithmetic; it is wrong above two players and is a known divergence, not a contract.

---

## 015: Multiplayer beyond two players is a day-one requirement

**Date:** 2026-08-05

**Supersedes the player-count framing of** [ADR 001](#001-mvp-is-pass-the-phone-two-player-not-solo-chain-building)
(ADR 008 superseded it on the *device* axis; this covers the *count*). **Corrects**
[ADR 008](#008-multi-device-server-authoritative-play-is-the-core-requirement) and
[ADR 012](#012-async-correspondence-is-a-first-class-mode-durable-store-authoritative), both of which
are written for two players throughout.

**Context:** Every prior ADR assumes a pair. The two-player prototype is not the target — the game is
more interesting with more people, and the whole point of strike-based scoring
([ADR 014](#014-round-and-match-are-separate-layers-the-round-engine-names-a-loser)) is a standings
table, which is degenerate at two.

**Decision:** N > 2 ships day one. `playerCount` has no upper bound at the round engine.

**Rationale:** At the round layer this costs almost nothing — rotation is modulo `playerCount`, and the
round reports the *index* of the player who failed rather than "the other player." Retrofitting it
later is not similarly cheap: it would touch the Game entity, per-player clock and deadline state, the
session layer's turn notification, and every client surface built around a single opponent. This is a
cheap decision now and an expensive one later, which is the definition of a thing to front-load.

**Consequences:**
- The Game entity holds a **player list, not a pair**, and clock/deadline state is **per player**.
- **"The other player" is not a valid concept anywhere** in the system — not in the engine, the session
  layer, or a client.
- What a failure *costs* remains a match-layer question
  ([ADR 014](#014-round-and-match-are-separate-layers-the-round-engine-names-a-loser)).
- Open matchmaking pools stay out of scope ([ADR 012](#012-async-correspondence-is-a-first-class-mode-durable-store-authoritative));
  N-player games are created the same way two-player ones are, by link.

---

## 016: Cast IDs are Wikidata QID strings; ID adaptation is loader-side

**Date:** 2026-08-04

**Refines** [ADR 009](#009-validation-is-precomputed-offline-and-served-in-process--no-per-turn-external-api)
(written as generic `movie_id → set(actor_id)` before the source was settled) and follows from
[ADR 010](#010-wikidata-cc0-is-the-data-source-tmdb-is-dropped).

**Context:** The graph artifact keys every node by its Wikidata QID string (`"Q23844"`) — movies,
actors, and the `entities` index alike. The Kotlin `:core` still declares `id: Int` and
`castIds: Set<Int>`, left over from the dropped TMDB source, and does not match the data it would have
to consume.

**Decision:** **QID strings are the validation contract.** The ETL emits them and must **never**
pre-map them to integers or any other compact ID. An engine that wants a different ID type performs
that mapping in its own loader, on the far side of the artifact boundary.

**Rationale:** The key space is a property of the *data*, not of whichever engine happens to read it.
Pre-mapping in the ETL would bake one consumer's preference into a shared artifact, break the ability
to trace any node back to Wikidata, and force a rebuild whenever a second consumer wanted something
different. This is a one-way door — it is the artifact's key space, and everything written against the
artifact depends on it.

**Consequences:**
- `:core`'s `Set<Int>` is **stale and carries no authority**; the data wins. Reconciling it also means
  updating the call sites across `:backend` and `:app` that consume `Move` and `GameState`, since
  retyping the IDs breaks the Gradle build.
- [ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md) specifies **opaque strings**, bound to QIDs — it does
  not assume integer identity or ordering.
- Identity is the ID alone; a QID may legitimately be reused across the two entity types without
  collision, so repeat detection is per-type
  ([ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md) R5, R12).

---

## 017: The conformance spec is authoritative over the engine implementation

**Date:** 2026-08-05

**Supersedes** the interim position that the code and its tests were the spec — itself adopted when
`GAME_SPEC_V2.md` was retired.

**Context:** Retiring `GAME_SPEC_V2.md` left `GameEngine.kt` and its tests as the only record of the
rules, and [issue #17](https://github.com/zws33/bacons_law/issues/17) documented that six of the
engine's twelve behaviors had lost test coverage in the process. That position is untenable while the
stack itself is up for reevaluation: "the code is the spec" ties the game's rules to an implementation
that may not survive the planning session, and offers nothing to grade a rewrite against.

**Decision:** [ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md) is the **round engine's spec of record** —
rules R1–R15 plus a numbered conformance suite, deliberately language- and framework-agnostic. It is
authoritative over `kotlin/core/.../GameEngine.kt` and its tests, which are prototype code; the spec
records where they diverge from it rather than deferring to them.

**Rationale:** The rules outlive any implementation of them. A spec that generates a test suite in any
stack is precisely what makes the stack decision reversible — without it, choosing a language is also
silently choosing where the rules live.

**Consequences:**
- Engine behavior changes go to the **spec first**, then the implementation.
- Whatever the engine is rewritten as is graded against the numbered suite; issue #17's coverage gap is
  absorbed by it rather than fixed separately against `Set<Int>`.
- Known divergences are recorded in the spec, not silently tolerated: the prototype reports a winner
  instead of a loser, uses `Int` IDs
  ([ADR 016](#016-cast-ids-are-wikidata-qid-strings-id-adaptation-is-loader-side)), lacks construction
  validation, and has repeat tests whose fixtures don't isolate the repeat rule.
- The spec's own **Open questions** (failure reason codes, opening-player index, clock-expiry
  ownership, chain-length limits) are live inputs to the planning session, not oversights.
