# Decision Log

Lightweight ADR-style record of key technical and product decisions.

> **001–007** are the original Kotlin/Android decisions, largely superseded. **008–013** established
> the current architecture — a server validating moves against a precomputed Wikidata graph built by a
> Python ETL. **014–017** record decisions made since that were previously only in `AGENTS.md`: the
> round/match split, N-player multiplayer, the QID contract, and the conformance spec's authority.
> **[018](#018-the-game-is-turn-based-real-time-is-a-time-control-not-an-architecture) is the most
> consequential recent change and amends 008, 011, and 012**: the game is turn-based, real-time is a
> time control rather than an architecture, and the WebSocket transport — along with the
> single-instance constraint it implied — is dropped. Read it before acting on anything in 008–012
> about transport, presence, broadcast, hosting, or instance count. **019** records the first
> decision this project made from measurement rather than reasoning — the graph's degree-1
> population is acceptable and cap rescue is rejected — and its evidence is
> [investigation 001](investigations/001-actor-degree-distribution.md). **020** is the first decision
> out of the planning session: typeahead resolves server-side, with the client-side index deferred
> behind a `suggest()` seam. **[021](#021-a-refused-move-is-rejected-not-lost-the-round-engine-gains-an-outcome-taxonomy)
> amends the round engine's contract** — a repeat or wrong-type submission is rejected rather than
> losing the round, `forfeit` carries a reason, and round termination is stated as a joint guarantee
> across the engine and the session layer. It resolves the conformance spec's highest-priority open
> question and is the largest behavioral change that spec has taken. **022 and 023 settle identity and
> the client together**, and are best read as one decision: web is the primary client and native is a
> showcase follow-up (023), which is what makes a device-anchored token insufficient and replaces it
> with a third-party authenticated account (022, superseding 013). A consequence worth knowing: 018
> addressed "it's your turn" to a push token on a device, and identity is no longer a device, so
> **the notification channel is reopened** — 022 records the two facts that bound it and leaves the
> choice undecided.
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

> **Amended twice.** The core decision — multi-device play with the server authoritative over game
> state — **holds and is not in question.** Three things below do not:
>
> - The in-process per-room `Mutex` is demoted by
>   [ADR 012](#012-async-correspondence-is-a-first-class-mode-durable-store-authoritative) §4 in favour
>   of optimistic concurrency (version/CAS) on the durable store. Read "this is the v1 design" as
>   historical.
> - **The WebSocket transport is dropped** by
>   [ADR 018](#018-the-game-is-turn-based-real-time-is-a-time-control-not-an-architecture). Clients
>   submit moves over request/response and learn of opponents' moves by polling + push. The
>   "horizontal scaling is a deferred pair" consequence below is **void**: the broadcast half was an
>   artifact of holding sockets, and the locking half is CAS. Scaling is neither paired nor blocked.
>   ADR 018 §4 also corrects the concurrency rationale — two *players* cannot contend for one turn; the
>   real writers are duplicate submissions, deadline adjudication, and match-level quits.
> - The two-player framing is superseded by
>   [ADR 015](#015-multiplayer-beyond-two-players-is-a-day-one-requirement).

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

**Context:** The intuitive approach validates "did this actor appear in this movie?" with a movie-API call per turn — the Python showcase did exactly that (a TMDB credits call per movie move). [CASE_STUDY.md](investigations/000-system-design-case-study.md) (§2–3) shows this is backwards: precompute the actor↔movie relationship once, offline, and the per-turn check collapses to an O(1) set-membership lookup. The system is connection-bound, not compute-bound; the connection check is the cheapest thing in it. *(The "connection-bound" half of that last clause is retracted by [ADR 018](#018-the-game-is-turn-based-real-time-is-a-time-control-not-an-architecture) — there are no persistent connections. The decision below does not depend on it: precomputed in-process validation is binding regardless of transport, and "the connection check is the cheapest thing in the system" is exactly as true over HTTP.)*

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

> **The language choice is reopened, and the hosting decision has lost its premise.** The
> *offline/online split* (Python ETL, everything else online) **holds**. "Server: Kotlin/Ktor," "reuse
> the pure `:core` engine as-is," and "the running system stays all-Kotlin" are **provisional**: the
> whole application build-out, stack included, is to be reevaluated in a planning session. See
> [`../AGENTS.md`](../AGENTS.md).
>
> **The hosting rationale below is void.**
> [ADR 018](#018-the-game-is-turn-based-real-time-is-a-time-control-not-an-architecture) drops
> persistent WebSockets, which was the entire reason scale-to-zero and multi-instance autoscaling were
> ruled out. The second clause of that rationale — "in-process session state + graph" — was **never a
> multi-instance argument**: the graph is ~21 MB, read-only, and identical everywhere, so N instances
> each load a copy and coordinate nothing. It survives only as a *cold-start* consideration, to be
> measured rather than assumed. **Hosting is an open planning-session question**, Fly.io included.
>
> Note also that the "server is connection-bound (CASE_STUDY §6)" premise in the Context below is
> itself what ADR 018 overturns.

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

> **Amended by [ADR 018](#018-the-game-is-turn-based-real-time-is-a-time-control-not-an-architecture).**
> The **requirement set survives intact** and is still the durable part of this ADR. Three things
> change:
>
> - **Real-time is no longer a mode to build.** §6's "correspondence-first, then real-time as an
>   additive layer (WS transport + presence + pub/sub + the clock subsystem)" becomes
>   correspondence-*only*; live play is a deferred non-functional requirement.
> - **§2's `mode` as per-game config is replaced** by storing a deadline as data — `turn_duration` plus
>   `deadline_at`. A 60-second turn and a 3-day turn are the same field, so there is no mode enum and
>   no second code path.
> - **§5's two clock models collapse to one.** The per-move deadline (timestamp, lazily swept) is
>   built; the running server-authoritative chess clock is not. Clocks remain session-layer state and
>   still never enter the engine.
>
> §1 (durable store authoritative, never behind a TTL), §3 (transport-agnostic move core), and §4
> (optimistic concurrency) all hold — though ADR 018 §4 corrects *why* §4 is needed.

**Amends [ADR 008](#008-multi-device-server-authoritative-play-is-the-core-requirement):** the in-process
per-room `Mutex` is demoted (below). **Supersedes** parts of the ROADMAP "out of scope" list — turn
timers and game-history persistence move *in scope*. ~~**[ADR 011](#011-kotlinktor-server--python-etl-single-flyio-instance-not-cloud-run)
survives** — real-time still requires persistent WebSockets + in-process graph on a single Fly
instance.~~ (Void — see the ADR 018 note above.) Identity is split into
[ADR 013](#013-persistent-player-identity-device-anchored-first).

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

> **Superseded by [ADR 022](#022-identity-is-a-third-party-authenticated-account).**
> The **requirement survives** — identity must outlive a room, span days, and back a "my games" inbox.
> The *mechanism* does not. Device-anchored-only was chosen to avoid building auth before the game was
> playable; that constraint was lifted once a third-party provider removed the build cost, and
> [ADR 023](#023-web-is-the-real-client-native-is-a-showcase-artifact) made web the primary client,
> where a device-anchored token is not durable enough to hold a correspondence player's games.
> The deferred "account upgrade path" described below is no longer deferred — it is the design.

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
  *(Two of those four — failure reason codes and clock-expiry ownership — were closed by
  [ADR 021](#021-a-refused-move-is-rejected-not-lost-the-round-engine-gains-an-outcome-taxonomy) on
  2026-08-09. This ADR's decision is unaffected; the list is left as written, being a record of what
  was open at the time.)*

---

## 018: The game is turn-based; real-time is a time control, not an architecture

**Date:** 2026-08-06

**Amends [ADR 008](#008-multi-device-server-authoritative-play-is-the-core-requirement)** (the
WebSocket transport and the "horizontal scaling is a deferred pair" consequence),
**[ADR 011](#011-kotlinktor-server--python-etl-single-flyio-instance-not-cloud-run)** (the
single-long-lived-instance hosting constraint loses most of its premise), and
**[ADR 012](#012-async-correspondence-is-a-first-class-mode-durable-store-authoritative)** (mode as
per-game config; real-time as an additive transport layer). The server-authoritative core of ADR 008,
the durable-store requirements of ADR 012, and the offline/online split of ADR 011 all **survive
unchanged**.

**Context:** [CASE_STUDY.md](investigations/000-system-design-case-study.md) §1 names the load-bearing property as "the game is
real-time and turn-based" and treats it as one thing. It is two, and only one of them is a rule.
**Turn-based is a rule of the game. Real-time is a time-control setting** — the way blitz is a setting
in chess, not a different architecture.

Taking them as one compound property led the case study to identify its central constraint as
"managing many long-lived, **mostly-idle** WebSocket connections" (§2). That adjective is the
counter-argument: a persistent bidirectional connection carrying a few messages per minute is a
mechanism without a workload. The consequences propagated well past the transport — §5's cost model is
built entirely on connection-holding and broadcast egress, and §6's language evaluation is *selected*
by it (green threads vs. event loops, memory per idle socket, built-in presence tracking, broadcast
fan-out). None of those criteria survive the removal of sockets, which means the assumption was
silently choosing the stack.

Two further observations settled it:

- **Real-time degrades as player count grows, and N > 2 is a day-one requirement
  ([ADR 015](#015-multiplayer-beyond-two-players-is-a-day-one-requirement)).** With four players on a
  60-second clock, each waits ~3 minutes between turns, all four must be simultaneously present and
  attentive, and one disconnect stalls everyone. Correspondence is indifferent to N. Live play is
  effectively a two-player mode, and ADR 012 and ADR 015 were in unnoticed tension.
- **The game rewards recall and strategy, not reaction time.** Nothing in the rules is decided by
  milliseconds, so the latency budget for delivering an opponent's move is seconds, not frames.

**Decision:**

1. **Correspondence is the primary and only gameplay mode built.** Live play with a running chess
   clock is dropped from the build, retained as a deferred non-functional requirement (below).
2. **No persistent-socket transport.** Move submission is request/response. The opponent learns of a
   move by **adaptive polling** (~2s while the game view is foregrounded and it is not your turn;
   stopped when backgrounded) plus **push notification** to the device-anchored token
   ([ADR 013](#013-persistent-player-identity-device-anchored-first)). The player who moved sees the
   result in their own response. This yields a perceived-live experience with no socket, no presence
   service, and no broadcast channel.
3. **Deadlines are stored as data, not as a mode.** A turn deadline is `turn_duration` plus a
   `deadline_at` timestamp. A 60-second turn and a 3-day turn are the same field at different values.
   This **replaces ADR 012 §2's framing of `mode` as per-game config** with a branch-free
   representation: there is no `realtime | correspondence` enum threading through the codebase, and
   therefore no second system to build.
4. **Optimistic concurrency (version/CAS) is retained, with a corrected rationale.** ADR 008 justified
   serialization by "two devices can send near-simultaneous messages"; by the rules, two *players*
   cannot contend for the same turn. The real sources are:
   - **Duplicate submission** — a slow request plus a user re-tap or a client retry. Both requests read
     the same version, both pass the turn check, both write; the move lands twice and a player is
     skipped. This is one player racing themselves, so the turn rule does not help.
   - **Deadline adjudication** — whatever resolves an expired deadline is not a player, and it can fire
     while that player submits at the last second. Keeping deadlines (§3) guarantees this writer exists.
   - **Match-level quit** — [ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md) scopes `forfeit` to the
     player on turn, but notes that quitting the *match* is a match-layer event; that one is not
     turn-scoped.

   What is dropped is **coordination infrastructure** — no distributed lock, no external coordination
   service, no in-process `Mutex`. What remains is a version column and a `WHERE version = ?` clause.
5. **Horizontal scaling is no longer a deferred pair, and no longer blocked.** ADR 008 held that
   scaling required coordinated locking *and* an inter-instance broadcast channel. The broadcast half
   was purely an artifact of holding sockets; the locking half is CAS on the store. Both are resolved.

**On the in-process graph and instance count.** AGENTS.md, README.md, and ADR 011 all state that
persistent WebSockets *and the in-process graph* together force a single instance. Only the first
clause was ever true. The graph is ~21 MB, read-only, and identical on every instance; N instances each
load their own copy and coordinate nothing. **The in-process graph is an argument about cold-start
cost, not about instance count.** It remains a mild argument against scale-to-zero — measurable as
artifact load time at boot, and to be measured rather than assumed, since turns are minutes-to-days
apart.

**Consequences:**

- **The stack decision is un-biased.** The planning session evaluates languages on ordinary
  request/response criteria. CASE_STUDY §6's concurrency-model comparison no longer selects for
  anything; a boring stack is now fully admissible.
- **Hosting is reopened.** ADR 011 rejected scale-to-zero platforms specifically because of persistent
  sockets. That premise is gone. The remaining question was artifact load time — **now measured, and
  it is not an obstacle:** the 21.4 MB `v1` artifact reads, parses, and converts to O(1)-membership
  sets in **~175 ms** (CPython 3.14 / stdlib `json`, the slowest realistic option; Node and JVM parse
  faster). Against turns that are minutes to days apart, a sub-second cold start is invisible.
  **Scale-to-zero is therefore viable**, and hosting is a free choice on ordinary grounds — cost,
  operational simplicity, familiarity — rather than a constrained one.
- **Three seams keep live play cheap to add later**, and are the whole cost of deferring rather than
  dropping it:
  - Keep the move core transport-agnostic — `(player, gameId, validatedMove) -> result` as a plain
    function, per ADR 012 §3, which already required this. No HTTP types in domain logic.
  - **Emit a notification event; do not call the notifier.** If move handling directly sends the push,
    adding a delivery mechanism later means editing the move path. Emitting "game X advanced to player
    B" for a delivery layer to consume keeps mechanisms pluggable. This is the one item genuinely
    expensive to retrofit.
  - Store the deadline, not the mode (§3 above).
- **A client-generated move ID for idempotency is recommended but not mandated.** CAS *rejects* a
  duplicate submission, which surfaces to the player as an error for something that in fact succeeded;
  an idempotency key returns the original result instead. Better UX for the dominant failure mode.
- **Typeahead, not gameplay, is the highest-frequency operation in the system.** CASE_STUDY §2 already
  identified name resolution as the real hard problem and then spent the architecture budget on
  transport. With sockets gone, the typeahead over ~89k entities is the load path worth designing —
  debounced request/response, or shipped to the client outright.
- **The case study loses its two most ornate sections** (§5's connection cost model, §6's concurrency
  comparison) as live analysis. They are preserved as dated record with superseding markers. The
  replacement is a stronger result: a designed-for workload that the game's own rules ruled out.
- **Unchanged:** server-authoritative state, the precomputed in-process graph, the engine/data
  co-location, the pure round engine, the durable-store requirement set (serializable, survives
  restarts, spans days, CAS-able, never behind a TTL), and device-anchored identity.

---

## 019: The graph's degree-1 population is acceptable; cap rescue is rejected

**Date:** 2026-08-06

**Evidence:** [investigation 001](investigations/001-actor-degree-distribution.md) — measured
against `graph/v1` (47,624 movies · 89,074 actors · 456,129 edges) and all 102 raw partitions.
That document is a record, not authority; this ADR is where its conclusions bind.

**Context:** A player whose every graph neighbour is already in the chain has no legal move. The
round ends and [ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md) names them the loser, identically to
a player who guessed wrong. Before building a server against the artifact, the question was whether
that situation arises often enough to change the data, the rules, or neither.

**Framing, stated because it decides the answer:** naming an actor whose only credit is the film in
play is a **legitimate winning move**, not an exploit. Knowing an actor has one credit is precisely
the knowledge this game tests, and obscurity is the skill gradient rather than something to
flatten. The question is only whether the knowledge required to end a round is *proportionate to
the reward* — cheap kills compress rounds; earned ones are the game working.

**Measurements:**

- **45.9%** of actor nodes (40,906 of 89,074) are degree-1, and **42.3%** of films contain one.
- Both numbers are misleading. Degree-1 actors have a **median of 4 sitelinks** against 11 for
  multi-credit actors. Requiring the round-ending actor to have merely ten language Wikipedias cuts
  availability to **15.2%** of films; twenty-five cuts it to **3.8%**.
- Among the **100 most famous films**: **11%** offer a round-ending move via a moderately-known
  one-credit actor, **2%** via a well-known one.
- **83.95%** of degree-1 actors are genuine one-credit performers; only 6,565 are cast-cap
  artifacts.

**Decision:**

1. **No ETL dial change.** `cast_cap=15`, `min_cast=3`, and `min_sitelinks=5` stand. The rate at
   which the graph offers a cheap round-ender is a skill filter, not a defect.
2. **Cap rescue is rejected**, not deferred. Restoring a truncated actor's next-best edge reduces
   nameable round-enders by 8.9% at a ≥10 sitelink floor and 1.0% at ≥50 — worth least exactly
   where the problem matters most. Its secondary justification (false rejections on a truncated
   actor's other films) falls to the same number: those actors are median-3-sitelink people, so
   those films are unlikely to be named either.
3. **No new engine or session-layer rule.** The exhausted-frontier case is rare enough in nameable
   terms that the current behaviour — the player on turn is the loser — is defensible. The policy
   question stays open in the conformance spec but is not blocking.

**Rationale — the mechanism worth remembering:** `cast_cap` ranks by the *actor's own* sitelinks,
so **being truncated is the notability filter operating.** An actor who appears in several films
and survives the cap in none of them is thereby demonstrated to be obscure. This is why cap rescue
cannot help: the population it repairs is more obscure than the population it leaves behind. The
expectation going in was the opposite — that reaching several films implied some recognition — and
it was wrong.

**Consequences:**

- **Do not re-propose cap rescue** without new evidence. It was measured and rejected, not skipped.
- **`min_sitelinks` gates films, not actors** ([extract.py](../etl/src/etl/extract.py) filters
  `?filmSitelinks` only). That is the mechanism admitting 40,906 leaf actors, and it is now a
  known, accepted property rather than an oversight.
- **Issue #19's confound is negligible here** — nine QIDs, 0.02% of degree-1 actors, independently
  reproducing the issue's own list. Its query fixes remain worth doing for correctness; they will
  not move these numbers.
- **The risk, such as it is, sits in famous films rather than obscure ones.** Filtered for
  nameability, notable films carry *more* round-enders (26.0% vs. 15.2%) because their one-credit
  members are themselves more notable. Absolute rates stay low, so this changes the explanation
  and not the decision — but it inverts the intuition the investigation started from.
- **Unmeasured and still open:** whether players actually find these moves (playtest, not graph),
  and how chain length raises the rate as degree-2+ actors exhaust their alternatives.

---

## 020: Typeahead resolves server-side; the client index is a deferred fast-follow

**Date:** 2026-08-07

**Evidence:** Direct measurement of `graph/v1`'s `entities` map — counts and serialized sizes. The
load and latency figures below are arithmetic on assumed conditions, not measurements, and are
labelled as such. No investigation document: the measurements are small enough to state here in
full.

**Context:** Nothing had been designed for name resolution, and it is the highest-frequency
operation in the system by a wide margin. Players type English names, the engine consumes QIDs, and
136,689 entities sit between the two. The open question was where resolution runs — server-side
against the in-memory map with a debounced client, or ship the index to the client and remove the
endpoint.

**Two framings, stated because they decide the answer:**

1. **The typeahead must search the full corpus, never the legal moves.** At any turn the valid moves
   are exactly the previous entity's neighbours — ~9.6 actors per film (capped at 15), ~5.1 films
   per actor. A typeahead scoped to those would be trivially fast and would hand the player the
   answer, which is the opposite of a game about recall. This is why it is a 136,689-record search
   problem rather than a 15-record one, and it is not negotiable.
2. **Endpoint volume is not the axis; latency is — but latency only decides a one-way door.**
   Typeahead is the sole path in this system with a human-perceptible budget;
   [ADR 018](#018-the-game-is-turn-based-real-time-is-a-time-control-not-an-architecture)
   established that everything else is measured in seconds to days. That makes latency the dominant
   *measurement*. It does not make it the dominant *criterion*, because moving resolution to the
   client later discards nothing.

**Measurements:**

- `entities` holds **136,689 records** — 89,068 actors, 47,621 movies. Nine short of the manifest's
  136,698: the dual-typed QIDs from [Issue #19](https://github.com/zws33/bacons_law/issues/19), the
  same nine [investigation 001](investigations/001-actor-degree-distribution.md) found. `entities`
  is keyed by QID alone, so a film credited as a cast member collapses onto itself and loses one
  type.
- Minified, then gzipped: **1.89 MB** as emitted, **1.59 MB** reshaped to parallel arrays, **1.09
  MB** for labels alone. Raw: 7.93 / 5.72 / 2.43 MB.
- Reshaping removed 2.2 MB of raw structural overhead and only 0.30 MB of it survived compression —
  **the wire cost is content, not format.**
- **Arithmetic, not measured:** at correspondence pace, 1,000 concurrent games moving every four
  hours is ~0.07 moves/sec; at 5–10 debounced requests per composed move, **under 1 typeahead
  request/sec.**
- **Estimated, not measured:** a mobile round-trip puts server-side resolution near 200–400 ms p50
  and worse on a poor connection, against sub-millisecond client-side.

**Decision:**

1. **Typeahead resolves server-side**, against the entities map already in memory, with the client
   debouncing input. It is the smaller build and it ships first.
2. **The client-side index is deferred, not rejected.** ~1.6 MB gzipped is affordable on all three
   planned client runtimes. The trigger to build it is playtest evidence that the latency is felt —
   not a threshold set in advance.
3. **One seam is required now:** the client's suggestion call is an interface —
   `suggest(prefix) -> Candidate[]` — never a `fetch` inlined into an input handler. This is the
   entire cost of the deferral, and it is a fourth seam of the kind ADR 018 established.
4. **The search-optimised shape is derived server-side at boot, never in the ETL.** The artifact
   emits the neutral contract; folded search keys are a consumer concern exactly as ID adaptation is
   under [ADR 016](#016-cast-ids-are-wikidata-qid-strings-id-adaptation-is-loader-side). This also
   means the index format can change without a graph rebuild.
5. **Matching is on folded keys, indexed at word starts.** Unicode case folding (*not*
   `toLowerCase` — locale-sensitive, and it fails ß/ss), NFD decomposition with combining marks
   stripped, apostrophe and punctuation normalisation; each entity indexed under every word start so
   `matrix` finds *The Matrix*. Corpus and query are folded identically or the two never meet.
6. **Results are ranked, and sitelink count is the signal.** A three-character prefix matches
   thousands of entities; which ten are shown is the felt quality of the feature. Ranking is not
   optional polish.

**Rationale — the mechanism worth remembering:** `entities` carries labels, types, and years and
**no edges whatsoever.** Every fact about move validity lives in the adjacency maps. The natural
data seam and the trust seam are therefore the same seam: the index can be shipped to a client
without disclosing a single answer — only the answer *space*, which players are entitled to know.
That is what makes the deferral safe rather than merely cheap. Nothing forecloses the later option,
and the fallback that keeps it open is the same endpoint being built now.

**Consequences:**

- **The resolve endpoint is permanent, not scaffolding.** The server must re-resolve any submitted
  QID regardless — a client's claim that a QID exists and is of the type it says is not trustworthy.
  Shipping the index later adds a delivery path; it does not remove this one.
- **Ranking needs a schema bump, and it is cheap.** Sitelink counts are fetched
  (`WikidataRow.film_sitelinks` / `actor_sitelinks`) and used for `cast_cap`, then **dropped at
  `Edge`** and absent from `entities`. Surfacing them means changing `Edge`, `transform`, and
  `emit`, then re-running **transform and emit only** — the raw partitions already hold the data, so
  no re-extract and no network. This is independent of Issue #19's rebuild and should not wait for
  it.
- **The agenda's rationale for sequencing this first does not hold.** It argued that shipping the
  index shrinks the server's job and makes the stack and store decisions easier. The server keeps
  the endpoint either way, so those decisions are unchanged by this one. Deciding it first was still
  right — it is cheap and it settles the delivery question — but it is not a prerequisite.
- **Protobuf is not the lever**; do not re-propose it on size grounds. The payload is dominated by
  string content no schema can compress, and gzip already removes the structural overhead protobuf
  targets. Expect single-digit percentages. If the index is ever shipped, the real levers are
  brotli, encoding QIDs as delta-encoded integers rather than strings, and front-coding the sorted
  labels.
- **Fold consistency becomes cross-runtime when the second client lands.** Corpus keys are folded
  server-side, so each client folds only the short query — a small function, but it must agree
  across JS, Kotlin, and Swift. A shared fixture list of input/expected pairs, run as a test in each
  client, is the mitigation. Not needed for the first client.
- **Within the client, algorithm choice is nearly irrelevant** if the index is ever shipped.
  Pre-folded linear scan is 2–8 ms; a sorted array with binary search on the prefix range is
  sub-0.1 ms and about twenty lines; a trie is not perceptibly better and costs 10–50× the memory.
  The 200–400 ms placement gap is two orders of magnitude larger than any of them. Do not spend
  design effort here.
- **Unmeasured and still open:** whether players actually notice server-side latency (playtest, not
  arithmetic); and whether actor name collisions need a disambiguator. Movies got `year` in schema
  v2 and actors have none — at 89,068 actors the collision count is not zero. Adding one is an ETL
  schema change and should be batched with the sitelink change above.

---

## 021: A refused move is rejected, not lost; the round engine gains an outcome taxonomy

**Date:** 2026-08-08

**Context:** [`ENGINE_CONFORMANCE.md`](ENGINE_CONFORMANCE.md) named failure reason codes its
highest-priority open question. `RoundOver` recorded *that* a move lost, not *why*, so a repeat, a bad
connection, a wrong type, a give-up and a lapsed deadline were indistinguishable to a match layer that
must charge different penalties for them.

The question dissolved rather than being answered. Two of those five causes turned out not to be round
outcomes at all.

**Decision:**

1. **A repeat or a wrong-type submission is `Rejected`, not a round loss.** The round is unchanged, the
   turn does not advance, and the player submits again. Neither is a game event; the match layer never
   sees one.
2. **An unconnected move is the only way `playMove` ends a round.** Correct type, available, no edge —
   which is the failure the game is actually about.
3. **`forfeit` takes a reason** — `GaveUp` or `DeadlineLapsed`. The engine cannot infer it, having no
   clock, so the session layer supplies it. `RoundOver.reason` is one of `Unconnected | GaveUp |
   DeadlineLapsed`.
4. **Evaluation order is normative: type, then availability, then connection.** A rejection always wins
   over a round loss. A player who submits an already-played entity that also would not have connected
   gets a retry, not a loss.
5. **In-round repeat prohibition is not configurable.** It is the sole guarantee that a round is finite.
   Cross-round exclusion sets remain optional match-layer policy.
6. **Round termination is stated explicitly and split across two layers** — the engine bounds the
   chain; the session layer's deadline bounds the retry loop.

**Rationale — why rejections are not losses.** The required type is fully determined by the chain and
visible to the player; the played set is on their screen. Both conditions are prevented client-side,
re-checked server-side, and only then reach the engine, which is the last of three lines rather than
the first. A submission that fails either one is a client defect, and resolving it to a round loss
charges a player for their client's malfunction. [R15](ENGINE_CONFORMANCE.md) already applied exactly
this reasoning to malformed input — *"a malformed input silently resolving to a loss would end real
rounds incorrectly and charge a strike to a player who did nothing wrong."* This extends the existing
line one category out rather than drawing a new one.

**Rationale — why repeats stay in the engine and stay mandatory.** Two intermediate positions were
considered and rejected:

- *Move the check to a server-side pre-pass.* Rejected: the engine runs in-process with the graph, so
  the pre-pass and the engine are the same process reading the same chain twice, and `playMove` is left
  with an unenforced precondition. A caller that skips it appends a duplicate and corrupts the chain
  silently — the opposite of R13's "an invalid state must not be representable." It would also strand
  eight conformance cases at a layer with no spec.
- *Make it match-layer policy, configurable per mode.* This was actively adopted and then reversed. The
  constitutive/regulative test appears to classify it as policy — Leonardo DiCaprio was in *Shutter
  Island* whether or not either has already appeared, so the connection is factually real and
  forbidding it looks arbitrary. But **it is the only thing that makes a round terminate**: without it
  a chain cycles between two entities forever. A rule the game cannot terminate without is not a
  difficulty dial. Cross-round exclusions carry no such load, which is why R5's two clauses share an
  implementation and a `RejectionReason` but not a modality.

**Rationale — the termination guarantee is now joint, and that is new.** Before this change every
submission either advanced the chain or ended the round, so the engine alone bounded a round. A
rejection consumes nothing, and [R10](ENGINE_CONFORMANCE.md) denies the engine a clock, so a player can
submit repeats indefinitely and be refused forever. The engine now guarantees only that the *chain* is
finite; the turn deadline, in the session layer, is what bounds the round. Neither is sufficient alone.
**A rejected submission must not reset the deadline** — that would remove the only bound on the retry
loop.

**Consequences:**

- **This is the largest behavioral delta in the conformance suite**, and it *inverts* prior behavior
  rather than adding to it. The Kotlin prototype resolves every one of these cases to a loss; an engine
  ported from it unchanged fails them. Group C is renamed and rewritten, TC-09/TC-10 move into it, and
  TC-32/33/34 are new.
- **The typeahead's filters are specified by implication.** The client filters by required type and
  against the played set — both information the player already holds. This refines
  [ADR 020](#020-typeahead-resolves-server-side-the-client-index-is-a-deferred-fast-follow) without
  weakening it: the prohibition there is on scoping to the previous entity's *neighbours*, which would
  disclose the answer. The line is **filter on what the player already knows; never filter on what only
  the graph knows.** Type-filtering also halves the candidate set, which is incidental.
- **Rejections are unbounded at the engine**, so rate limiting becomes a transport concern. It was not
  one before, when a bad submission ended the round.
- **Wrong type MAY be enforced by the type system; repeat MUST NOT be.** An engine splitting
  `InProgress` by required type makes a wrong-type submission a compile error. Availability is a
  predicate over a runtime set and admits no such encoding. Static enforcement relocates the check to
  the boundary that deserializes untyped input; it does not remove it. Same MAY/MUST split as R14.
- **This narrows the stack decision slightly.** Agenda §3.1 already weighs how cleanly a language
  expresses the sealed-union state machine; static alternation enforcement is a further point for
  Kotlin and TypeScript over Python. The spec phrases it as MAY precisely so the two decisions stay
  independent.
- **`RoundOver.reason` is a persisted contract.** It is written into stored round results a match layer
  replays, so widening the enum later is cheap and changing its shape is not.
- **Not settled by this:** chain length limits. R17's bound of ~95,000 moves is a proof, not a usable
  cap, and the persistence and payload concern behind that question is untouched.

---

## 022: Identity is a third-party authenticated account

**Date:** 2026-08-09

**Supersedes [ADR 013](#013-persistent-player-identity-device-anchored-first).**
**Amends [ADR 018](#018-the-game-is-turn-based-real-time-is-a-time-control-not-an-architecture)** on
the notification path.

**Context:** ADR 013 chose a device-anchored token to avoid building an auth system before the game was
playable. That was a constraint from a period of prioritising a quick MVP, and it no longer applies.

**Stated reason:** auth avoidance is not required. A third-party implementation will be used; rolling
custom auth is explicitly not wanted.

**The durability problem.** A device-anchored token on web lives in script-writable storage. Safari's
tracking prevention clears that after roughly a week without user interaction for sites not installed
to the home screen. Correspondence play is the pattern that goes a week between visits, so under ADR
013's design on web, what ADR 013 listed as a rare accepted limitation ("a lost/wiped device loses that
player's games") becomes the routine case. **The current behaviour of that storage cap should be
verified before designing against its specifics** — the exact number of days is not the point, and this
claim has not been checked against current Safari behaviour.

**Decision:**

1. **Identity is an authenticated account, from a third-party provider.** No rolled auth: no password
   hashing, no session-token minting, no reset flows, no credential storage in this project.
2. **The provider issues a JWT; the server verifies it against the provider's JWKS.** That is the whole
   integration surface on the server side.
3. **A Player record remains in this project's own store**, keyed to the provider's subject claim. The
   provider owns credentials; this project owns player state.
4. **Provider selection is deferred** and is coupled to the durable-store decision — see Consequences.

**Supporting analysis** — not the reason the decision was made, recorded because it bears on later
work:

- **ADR 013's two accepted limitations do not ship.** It accepted that a lost device loses its games
  and that one identity cannot play on two devices, and named an upgrade path to fix both. That path is
  now the design.
- **This does not constrain the stack.** JWKS verification exists in every ecosystem under
  consideration. The provider's frontend SDK is where quality varies, and that is a web/TypeScript
  concern regardless of what the server is written in.
- **A non-push notification channel becomes possible.** An authenticated account carries a verified
  email address. What to do with that is not decided here — see below.

**Consequences:**

- **Auth and the durable store may be one decision.** Several providers bundle them (Postgres + auth;
  auth + document store). This collapses agenda §3.2 and this ADR into a single vendor choice if
  desired — with the caveat below.
- **Polling makes per-read pricing a store-selection criterion.** ADR 018 commits to ~2s adaptive
  polling while a game view is foregrounded, which is a read generator by construction. A store billing
  per document read converts the notification design into a running cost; a store on a fixed instance
  does not. Noted as a criterion for the store decision; no store is chosen here.
- **ADR 018's push token is no longer where a notification is addressed.** ADR 018 routes "it's your
  turn" to a push token on a device; identity is no longer a device. **ADR 018's seam #2 already
  anticipated the shape of this** — "move handling emits a notification event rather than calling the
  notifier" — so whatever the delivery layer does, the change lands there and touches nothing in the
  move path. That seam was described as the one item genuinely expensive to retrofit.
- **This adds identity, not a player-directory.** Open matchmaking pools were out of scope before this
  ADR and remain so; nothing here is an argument for changing that.

**Not decided here.** Both follow from this ADR and neither has been chosen:

- **Which notification channel is primary.** Two facts bear on it. An authenticated account carries a
  verified email address, so a channel exists that needs no install, service worker, or APNs
  relationship. And web push on iOS requires a home-screen install
  ([ADR 023](#023-web-is-the-real-client-native-is-a-showcase-artifact) makes web the primary client),
  so push does not reach every player on the platform this project is shipping to. What follows from
  that pair — email as the floor with push as an upgrade, push with an email fallback, or something
  else — is open.
- **Whether signing in is required to play.** ADR 013's design let a player start immediately. Requiring
  an account at first run is one option; anonymous play with a prompt to claim the games later is
  another, and ADR 013's own "non-destructive upgrade" requirement already describes the machinery for
  it. The trade is first-run friction against players silently losing match history, and it has not
  been weighed. Provider choice interacts with this: magic-link and passkey sign-in cost less at first
  run than password creation.

---

## 023: Web is the real client; native is a showcase artifact

**Date:** 2026-08-09

**Amends [ADR 002](#002-androidkotlincompose-for-mvp-client)** (Android as *the* client) and settles
planning agenda §3.4.

**Context:** The client platform was fully open. In the tree sits an unmaintained Android/Compose app
built for the dropped pass-the-phone model — 18 source files, most of them written against assumptions
that no longer hold. Web was untried. The agenda flagged that push is straightforward on mobile and
clunkier on web, and that this coupled the client decision to notification design more tightly than it
looked.

**Decision:**

1. **Web is the primary client.** It is the easiest to deploy to real users, and it ships first.
2. **Native clients are follow-ups built primarily for showcase purposes**, not to acquire users.
3. **No app-store deployment for now.** The obstacles in deploying to the Apple and Play stores are
   being avoided deliberately. If the project takes off after a real launch such that the cost — in
   money and in attention — is justified, app-store deployment gets revisited then. A native client
   can exist and be demonstrated without being published.

**Stated reason:** web is the easiest way to get this in front of real users, and the app-store
deployment process is not worth navigating before there is evidence anyone wants the game.

**Supporting analysis** — not the reason the decision was made, recorded because it bears on later
work:

- **Install friction is paid per player, and multiplayer at N > 2 ships day one.** Getting three
  friends into a match over the web is one link; natively it is three installs.
- **Two decisions already taken are waiting on playtests.**
  [ADR 020](#020-typeahead-resolves-server-side-the-client-index-is-a-deferred-fast-follow) defers the
  client-side typeahead index with the trigger "playtest evidence that the latency is felt," and
  [ADR 019](#019-the-graphs-degree-1-population-is-acceptable-cap-rescue-is-rejected) leaves open
  whether players find dead-end moves at all. Both need players.
- **A client cannot share the engine in any useful way.** The connection check requires the 21 MB graph
  and graph co-location is a binding boundary. What a client *can* validate — correct type, not already
  played — is [ADR 021](#021-a-refused-move-is-rejected-not-lost-the-round-engine-gains-an-outcome-taxonomy)'s
  typeahead filtering, which needs the chain and nothing else. `AGENTS.md`'s "shareable across server
  and clients" is a true statement about purity and a weak argument for code reuse. This matters
  because it removes a reason to prefer a native client, and a criterion from the stack decision.

**Consequences:**

- **This is what forces [ADR 022](#022-identity-is-a-third-party-authenticated-account).**
  Device-anchored identity is durable on native and is not on web. Choosing web is what turned ADR 013's
  deferred account upgrade into a requirement.
- **Web push does not reach every player.** It works on most browsers and requires a home-screen
  install on iOS. Which channel is primary is not decided — see ADR 022, *Not decided here*.
- **The stack decision is now nearly free of client constraints.** Client language is decoupled, engine
  sharing is worth little, and auth is provider-issued JWTs verifiable anywhere. Agenda §3.1 should be
  evaluated on ecosystem maturity, how cleanly the language expresses the round engine's sealed-union
  state machine, deployment simplicity, and — from ADR 021 — whether static enforcement of type
  alternation is wanted. **Shared types with the client is no longer a meaningful criterion.**
- **Stated alongside this decision: single-language velocity is a non-factor.** A mix of languages is
  acceptable where it suits the project's goals; TypeScript/JavaScript, Kotlin, Java, and Python are
  all comfortable. This removes "one language end to end" as an argument in the stack decision, in
  either direction.
- **`:app` is not the starting point for the native client.** It was built for pass-the-phone play
  against a per-turn TMDB call; both are gone. It remains reference-only per `AGENTS.md`.
- **ADR 020's cross-runtime fold consistency is deferred with native.** Search-key folding must agree
  across JS, Kotlin, and Swift, mitigated by a shared fixture list. ADR 020 already says this is not
  needed for the first client.
- **A native client's own decisions are not made here.** Which platform, whether it shares an engine,
  and what it is built with are open. This ADR settles only that native is a follow-up and is not
  store-deployed for now.
