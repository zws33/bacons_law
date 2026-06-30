# Agents Guide — Bacon's Law

A real-time trivia game based on "Six Degrees of Kevin Bacon." Two players on **separate devices**
take turns naming movies and actors to build a chain of connections; each answer must connect
factually to the previous one. A **Kotlin/Ktor server** owns authoritative game state and validates
every move against a **precomputed actor↔movie graph** held in memory. First player who can't name a
valid connection loses.

**Target architecture:** a Python ETL precomputes a bipartite movie↔actor graph from **CC0 Wikidata**
data; the Ktor server loads it **read-only, in-process** at boot and validates a move with an O(1)
set-membership check — **no per-turn external API call**. The pure game engine is the existing Kotlin
`:core` module, reused unchanged. See [docs/CASE_STUDY.md](docs/CASE_STUDY.md) for the reasoning and
[docs/DECISIONS.md](docs/DECISIONS.md) (ADRs 008–011) for the decisions.

**Current status:** Pivoting to this direction (Phase 0 of [ROADMAP.md](ROADMAP.md)). `:core` is
reused as-is. `:backend` currently exists as the prior TMDB proxy and is being rebuilt into the
graph-backed session server (Phases 2–3). The `etl/` pipeline is not yet created (Phase 1). Two prior
efforts are preserved as reference, not maintained: the Kotlin/Compose Android client (`:app`) and
the Python/FastAPI showcase (branch `fullstack-py-ts-rewrite`, tag `python-fastapi-showcase`, docs
under [docs/python/](docs/python/README.md)).

---

## Repository layout

The repo root is intentionally **stack-agnostic** — it holds shared docs and meta only. Each
implementation/component is a **self-contained project in its own top-level directory** with its own
toolchain. Adding a new (polyglot) experiment is *adding a directory*, not restructuring the root.

```
bacons-law/               # stack-agnostic root — shared docs + meta only
├── docs/                 # shared knowledge: case study, engine spec, decisions; docs/python/ archive
├── kotlin/               # self-contained Gradle project — the Kotlin implementation
│   ├── core/             # Pure Kotlin/JVM — game engine + shared domain types. Zero platform deps. REUSED.
│   ├── backend/          # Ktor service. TODAY: TMDB proxy (prior phase). TARGET: graph-backed game
│   │                     #   server — loads the graph in-process, WS rooms, Redis live state, O(1) validation.
│   └── app/              # Android/Compose client. Secondary; modernized into a multi-device client later.
├── etl/                  # Python (planned, Phase 1) — offline batch pipeline. Pulls Wikidata (CC0),
│                         #   caps cast depth, emits the versioned graph artifact. Separate toolchain.
└── <future>/            # new experiments / components are new top-level dirs; the root stays neutral
```

Gradle commands run from `kotlin/` (that's where `settings.gradle.kts` and the wrapper live). Gradle
module notation (`:core`, `:backend`, `:app`) is unchanged — it's relative to the `kotlin/` project.

### `:core` — the pure engine (reused)

The game state machine: `GameState`, `Move` (`Move.Actor` / `Move.Movie`), `playMove`, `forfeit`. It
has no platform or I/O dependencies and **must stay that way**. `Move.Movie.castIds: Set<Int>` is the
validation contract; the engine checks `castIds.contains(...)` and makes no network calls. The
authoritative engine spec is [docs/GAME_SPEC_V2.md](docs/GAME_SPEC_V2.md).

### `:backend` → the game server

Currently a thin TMDB proxy (movie/person search, credits). The pivot rebuilds it into the
authoritative session server: load the precomputed graph at boot, serve a WebSocket channel per room
(`/ws/rooms/{code}`: join / resume / move / forfeit / broadcast), keep live room state in Redis,
serve typeahead/search from the local entity index. It depends on `:core`, never the reverse.

### `etl/` — the offline graph build (Python, planned)

A separate Python toolchain (`uv`/`ruff`) that runs offline, not in the request path. It produces the
versioned artifact the server loads. Python is the right tool for the data-wrangling here; the
polyglot split is allowed across the offline/online seam only (see ADR 011).

### `:app` — Android client (secondary)

Compose UI. Built for the old pass-the-phone model; will be modernized into a thin multi-device client
that renders server-pushed state (or replaced by a new web client — decided at Phase 4). It depends on
`:core` and never holds data-source credentials.

#### Android notes

For Android-specific tasks, prefer Google's `android` CLI if on PATH (`android version || android --help`)
for SDK install/update, emulator/device workflows, project discovery, and official docs. Use Gradle for
normal builds/tests. If `android` is not installed, say so and fall back to the Gradle + Android SDK flow.

---

## Environment Setup

**There is no TMDB key in the new architecture** — validation data comes from CC0 Wikidata, built
offline. Do not reintroduce a per-turn movie-API dependency.

- **ETL (Phase 1+):** runs offline; its Wikidata access needs no secret. Output is a versioned graph
  artifact consumed by the server.
- **Server:** needs `REDIS_URL` for live room state. In production these are injected via
  `fly secrets`; locally, export them in the environment.

---

## Build & Test Commands

Gradle commands run from `kotlin/`; the ETL runs from `etl/`. No build tooling runs from the repo root.

| Task | Command |
|------|------|
| Run `:core` unit tests | `cd kotlin && ./gradlew :core:test` |
| Run all JVM unit tests | `cd kotlin && ./gradlew test` |
| Build everything | `cd kotlin && ./gradlew build` |
| Run the server (when built) | `cd kotlin && ./gradlew :backend:run` |
| ETL (planned) | `uv run …` from `etl/` (separate toolchain) |

`:core:test` is the fast feedback loop for game logic.

---

## Deployment

Hosting is **Fly.io, not Cloud Run** — persistent WebSocket connections and in-process session state +
graph are incompatible with scale-to-zero / multi-instance autoscaling. The server runs as a **single
long-lived instance by design**; the per-room `Mutex` is authoritative for serializing room mutations.
The graph artifact is bundled with / loaded by the server at boot. Redis runs colocated on Fly. See
[ROADMAP.md](ROADMAP.md) Phase 5.

---

## Code Conventions

- **Indent:** per-language via `.editorconfig` (Kotlin/XML 2 spaces, Python 4).
- **Commits:** Conventional commit format — `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- **Kotlin style:** follow existing style; prefer pure functions and immutable data in `:core`.
- **Build versions:** declared in `gradle/libs.versions.toml`. Don't hardcode version strings.
- **Python (etl/):** `ruff` + `uv`; keep it self-contained and offline.

---

## Architecture Boundaries

**Keep `:core` pure.** No `android.*`, `androidx.*`, no I/O, no network — pure Kotlin/JVM so it is
testable on the JVM and shareable across `:backend`, `:app`, and future KMP targets. New game logic
goes in `:core` with a test.

**Validation is co-located with the graph, in-process.** The O(1) check holds **only** while the graph
and the validation logic share a process. **The engine/data seam must never cross a network hop** — do
not split the engine and the graph across services (CASE_STUDY §2/§6, ADR 009).

**Validation data is precomputed offline.** The actor↔movie relationship is built by the ETL into a
versioned artifact and loaded read-only at boot. **Do not add a per-turn external API call** to the
move path — that is the anti-pattern this architecture exists to remove.

**`castIds` is the validation contract.** `Move.Movie` carries a `Set<Int>` of cast member IDs. The
server populates it from the in-memory graph before passing a `Move.Movie` to `playMove`. The engine
makes no network calls.

**Redis is authoritative for live room state.** Live `GameState` lives in Redis per room, TTL'd.
Multi-device (many clients on one room) does not require multiple server instances; horizontal scaling
is a deferred pair (Redis-coordinated locking + Pub/Sub broadcast — ADR 008).

---

## What to Avoid

- **Do not put a per-turn movie-API call in the move path** — validation is precomputed offline and
  served in-process. (This is exactly what the Python showcase did wrong; it's the reason for the pivot.)
- **Do not split the engine from the graph across a network boundary** — co-location is load-bearing.
- **Do not add I/O to `:core`** — it must remain pure (no network, no Redis, no platform deps).
- **Do not reintroduce TMDB as a runtime dependency** — the data source is CC0 Wikidata, built offline.
  There is no TMDB key anywhere.
- **Do not bypass repeat detection** — `playMove` rejects reuse of an actor or movie already in the
  chain. This is a game rule, not a bug.
- **Do not add out-of-scope mechanics** — time limits, passes, challenges, scoring, accounts, and
  game-history persistence are deferred. See [docs/GAME_SPEC.md](docs/GAME_SPEC.md) and
  [ROADMAP.md](ROADMAP.md).
- **Do not use TV shows or documentaries** — movies only.

---

## Key Documents

| Document | Purpose |
|----------|---------|
| [docs/GAME_SPEC_V2.md](docs/GAME_SPEC_V2.md) | **Authoritative** spec for the pure game engine (rules + state machine) |
| [docs/CASE_STUDY.md](docs/CASE_STUDY.md) | System-design reasoning behind this architecture |
| [docs/DECISIONS.md](docs/DECISIONS.md) | ADR log; 008–011 cover the current direction |
| [ROADMAP.md](ROADMAP.md) | Phased plan; current work is Phase 0 (pivot) |
| [docs/GAME_SPEC.md](docs/GAME_SPEC.md) | Retained for product intent / out-of-scope (engine rules superseded by V2) |
| [docs/python/](docs/python/README.md) | Archived Python/FastAPI showcase docs |
