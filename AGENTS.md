# Agents Guide — Bacon's Law

A two-player Android trivia game based on "Six Degrees of Kevin Bacon." Players pass a phone, taking turns naming movies and actors to build a chain of connections. Every move is validated in real-time via a Kotlin/Ktor backend that proxies the TMDB API. First player who can't name a valid connection loses.

**Current status:** Game engine and TMDB data layer exist independently. The active work is wiring them into a connected game loop (Phase 1 of [ROADMAP.md](ROADMAP.md)).

---

## Module Map

```
bacons-law/
├── core/      # Pure Kotlin/JVM — game engine and shared domain types, zero platform dependencies
├── app/       # Android — Compose UI, ViewModels, HTTP client to :backend
└── backend/   # Ktor service — TMDB proxy, move validation, future game session management
```

### `:core`

Contains the game state machine: `GameState`, `Move`, `Player`, and `GameEngine`. This module has no Android or platform-specific dependencies and must stay that way. All game logic lives here. Both `:app` and `:backend` depend on `:core` — it is the shared domain layer.

### `:app`

Contains everything Android-specific:
- **`data/`** — Retrofit API client, `:backend` request/response models
- **`presentation/`** — Compose UI, ViewModels, `Repository`

The `:app` module depends on `:core` and calls `:backend` for all TMDB data. It never holds TMDB credentials.

### `:backend`

Contains the Ktor HTTP service:
- **Endpoints** — movie search, person search, movie credits (proxied from TMDB)
- **Normalization** — maps TMDB responses to `:core` domain models before returning them to clients
- **Credentials** — TMDB API key lives here only, never in any client module

The `:backend` module depends on `:core`, not the other way around.

---

## Environment Setup

TMDB API access requires a key that is **never embedded in any client binary**. The key belongs to `:backend` only — it must not appear in `:app` or any future client module as a `BuildConfig` field or hardcoded string.

**Production:** The key is stored in Google Secret Manager and injected into the Cloud Run service at runtime.

**Local development:** Add the key to `local.properties` at the project root for use by the `:backend` module:

```
TMDB_API_KEY=your_key_here
```

Get a free key at https://developer.themoviedb.org/docs/getting-started

Do not commit `local.properties`. The `:app` module does not read this key.

---

## Build & Test Commands

All commands run from the project root.

| Task | Command |
|------|---------|
| Build debug APK | `./gradlew :app:assembleDebug` |
| Run `:core` unit tests | `./gradlew :core:test` |
| Run all JVM unit tests | `./gradlew test` |
| Run Android lint | `./gradlew :app:lint` |
| Full local check (no device needed) | `./gradlew :core:test :app:assembleDebug :app:lint` |

**Note on instrumented tests:** `./gradlew :app:connectedAndroidTest` requires a connected device or running emulator. Prefer `:core:test` for fast feedback on game logic.

---

## Code Conventions

- **Indent:** 2 spaces (enforced by `.editorconfig`)
- **Commits:** Conventional commit format — `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`
- **Kotlin style:** Follow the existing code style. Prefer pure functions and immutable data in `:core`.
- **Build versions:** All dependency versions are declared in `gradle/libs.versions.toml`. Do not hardcode version strings in build files.

---

## Architecture Boundaries

**Keep `:core` pure.** It must not import `android.*`, `androidx.*`, or any platform-specific library. The game engine is pure Kotlin/JVM so it can be tested on the JVM and shared across `:app`, `:backend`, and future KMP targets. If you need to add game logic, add it to `:core` with a JUnit 5 test.

**TMDB credentials stay in `:backend`.**  All TMDB API calls are made by the `:backend` service. The `:app` module calls `:backend` endpoints — it never calls TMDB directly and must not hold a TMDB API key. Do not add a TMDB key as a `BuildConfig` field in `app/build.gradle.kts`.

**`castIds` is the validation contract.** `Move.Movie` carries a `Set<Int>` of TMDB cast member IDs. The `:app` layer is responsible for fetching these IDs from `:backend` and populating them before passing a `Move.Movie` to `playMove`. The engine itself does not make network calls.

---

## What to Avoid

- **Do not commit `local.properties`** — it contains the TMDB API key for local backend development.
- **Do not embed API credentials in any client binary** — the TMDB API key must never appear in `:app` or any future client module (iOS, web) as a `BuildConfig` field, hardcoded string, or bundled asset. All TMDB access goes through `:backend`.
- **Do not add Android dependencies to `:core`** — it must remain a pure Kotlin/JVM module.
- **Do not bypass repeat detection** — `playMove` rejects moves that reuse an actor or movie already in the chain. This is a game rule, not a bug.
- **Do not add MVP out-of-scope mechanics** — time limits, passes, challenges, and scoring are explicitly deferred. See [docs/GAME_SPEC.md](docs/GAME_SPEC.md#explicitly-out-of-scope-mvp).
- **Do not use TV shows or documentaries** — TMDB is queried for movies only. The game spec excludes non-theatrical content for MVP.

---

## Key Documents

| Document | Purpose |
|----------|---------|
| [docs/GAME_SPEC.md](docs/GAME_SPEC.md) | Source of truth for game rules and engine behavior |
| [docs/DECISIONS.md](docs/DECISIONS.md) | ADR-style log of key technical and product decisions |
| [ROADMAP.md](ROADMAP.md) | Phased development plan; current work is Phase 1 |
| [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md) | Detailed implementation plan for Phase 1 |
