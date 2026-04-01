# Agents Guide — Bacon's Law

A two-player Android trivia game based on "Six Degrees of Kevin Bacon." Players pass a phone, taking turns naming movies and actors to build a chain of connections. Every move is validated in real-time via the TMDB API. First player who can't name a valid connection loses.

**Current status:** Game engine and TMDB data layer exist independently. The active work is wiring them into a connected game loop (Phase 1 of [ROADMAP.md](ROADMAP.md)).

---

## Module Map

```
bacons_law/
├── core/    # Pure Kotlin/JVM — game engine only, zero Android dependencies
└── app/     # Android — Compose UI, TMDB API client, ViewModels
```

### `:core`

Contains the game state machine: `GameState`, `Move`, `Player`, and the top-level functions `startGame`, `playMove`, and `forfeit`. This module has no Android dependencies and must stay that way. All game logic lives here.

### `:app`

Contains everything Android-specific:
- **`data/`** — Retrofit API client, TMDB request/response models
- **`presentation/`** — Compose UI, ViewModels, `Repository`

The `:app` module depends on `:core`, not the other way around.

---

## Environment Setup

TMDB API access requires a key that is **not committed to source control**.

1. Get a free key at https://developer.themoviedb.org/docs/getting-started
2. Add it to `local.properties` at the project root:
   ```
   TMDB_API_KEY=your_key_here
   ```

Without this key, the app will compile but all TMDB API calls will fail at runtime. The key is injected as a `BuildConfig` field in `app/build.gradle.kts`.

Do not commit `local.properties`.

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

**Keep `:core` pure.** It must not import `android.*`, `androidx.*`, or any Android-specific library. The game engine is pure Kotlin so it can be tested on the JVM and reused for a future Go or web backend. If you need to add game logic, add it to `:core` with a JUnit 5 test.

**TMDB data stays in `:app`.** Cast validation requires a TMDB API call. The bridge between `:app`'s network layer and `:core`'s `playMove` function is the integration point that is actively being built. Wire through a ViewModel or Repository — do not let Retrofit types leak into `:core`.

**`castIds` is the validation contract.** `Move.Movie` carries a `Set<Int>` of TMDB cast member IDs. The `:app` layer is responsible for fetching these IDs from TMDB and populating them before passing a `Move.Movie` to `playMove`. The engine itself does not make network calls.

---

## What to Avoid

- **Do not commit `local.properties`** — it contains the TMDB API key.
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
