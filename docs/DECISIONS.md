# Decision Log

Lightweight ADR-style record of key technical and product decisions.

---

## 001: MVP is pass-the-phone two-player, not solo chain-building

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
