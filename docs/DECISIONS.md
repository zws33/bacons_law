# Decision Log

Lightweight ADR-style record of key technical and product decisions.

> ADRs 001–007 are the original Kotlin/Android decisions. ADRs 008+ cover the current direction — a
> Kotlin/Ktor server validating moves against a precomputed Wikidata graph built by a Python ETL.
> The archived Python/FastAPI showcase kept its own log at [`python/DECISIONS.md`](python/DECISIONS.md).

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

**Date:** 2026-06-29

**Supersedes:** [ADR 001](#001-mvp-is-pass-the-phone-two-player-not-solo-chain-building) (pass-the-phone was the single-device MVP, not the end state). Carries forward the substance of the Python showcase's ADR 009, re-expressed for the Kotlin trunk.

**Context:** Multiple devices connect to the same room over the network, and the backend owns authoritative game state. The single-device framing misleads design — most concretely, it makes the room store's concurrency model look like a non-problem ("turns are sequential, only one device") when two devices can send near-simultaneous messages to the same room.

**Decision:** Multi-device play is core, not a deferred enhancement. The Ktor server is the authoritative owner of game state; clients submit move *intents* over a WebSocket and render the state the server pushes back. Turns remain sequential as a game rule, but turn-validation and state-mutation are atomic *together* on the server — sequential turns are a rule the server enforces, not a guarantee that only one message arrives at a time.

**Consequences:**
- **Multi-device (clients) ≠ multi-instance (servers).** A single instance can hold thousands of WebSocket connections across thousands of rooms; multi-device does **not** by itself require horizontal scaling.
- **Single instance + per-room lock (Kotlin `Mutex`) is sufficient.** Concurrent moves to the same room are serialized by an in-process per-room lock. This is the v1 design.
- **Horizontal scaling is deferred and comes as a pair:** Redis-coordinated locking *and* Redis Pub/Sub broadcast (a second instance can't see the first's sockets). Build both or neither.
- This realizes the inversion anticipated in [ADR 007](#007-gameviewmodel-owns-game-state-for-phase-1-client-thins-in-phase-4): the server becomes the authoritative owner; `:app` thins to a state consumer.

---

## 009: Validation is precomputed offline and served in-process — no per-turn external API

**Date:** 2026-06-29

**Context:** The intuitive approach validates "did this actor appear in this movie?" with a movie-API call per turn — the Python showcase did exactly that (a TMDB credits call per movie move). [CASE_STUDY.md](CASE_STUDY.md) (§2–3) shows this is backwards: precompute the actor↔movie relationship once, offline, and the per-turn check collapses to an O(1) set-membership lookup. The system is connection-bound, not compute-bound; the connection check is the cheapest thing in it.

**Decision:** The actor↔movie relationship is precomputed offline into a bipartite graph (`movie_id → set(actor_id)`, `actor_id → set(movie_id)`) and loaded **read-only, in-process** into the server at boot. Move validation is `castIds.contains(...)` against the loaded graph — no network call in the hot path. The pure `:core` engine is unchanged; only its data source changes.

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

**Date:** 2026-06-29

**Supersedes the hosting choice of:** [ADR 005](#005-kotlinktor-backend-proxy-for-tmdb--credentials-never-in-client-binaries) (Cloud Run scale-to-zero is incompatible with persistent WebSockets).

**Context:** The server is connection-bound (CASE_STUDY §6). Kotlin is the strongest language on hand, with structured concurrency (coroutines / virtual threads) well-suited to many long-lived, mostly-idle connections, sealed classes that model the engine, and KMP reach for an Android client. The offline graph build is data-wrangling work where Python excels — and CASE_STUDY §6 blesses a polyglot split across the *offline/online* seam (but **not** across the engine/data seam).

**Decision:**
- **Server: Kotlin/Ktor.** Reuse the pure `:core` engine as-is; rebuild `:backend` from a TMDB proxy into the graph-backed authoritative session server (WS rooms, Redis live state, in-process graph). Modernize `:app` into a multi-device client later (secondary).
- **ETL: Python**, a separate offline toolchain (`etl/`) producing the versioned graph artifact.
- **Hosting: a single long-lived Fly.io instance**, not Cloud Run — persistent WebSocket connections and in-process session state + graph are incompatible with scale-to-zero / multi-instance autoscaling.

**Consequences:**
- The running system stays all-Kotlin (client + server + shared `:core`), preserving [ADR 002](#002-androidkotlincompose-for-mvp-client)'s all-Kotlin property; Python is offline-only.
- Redis holds live room state and is the coordination point if horizontal scaling is ever justified ([ADR 008](#008-multi-device-server-authoritative-play-is-the-core-requirement)).
- Egress is the dominant cost driver at scale (CASE_STUDY §5); a Cloudflare-front + cheap-origin posture is a future lever, not a v1 requirement.
