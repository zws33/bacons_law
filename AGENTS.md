# Agents Guide — Bacon's Law

A trivia game based on "Six Degrees of Kevin Bacon." Two players on **separate devices** take turns
naming movies and actors to build a chain of connections; each answer must connect factually to the
previous one. Games run in one of two modes (chess.com-style, chosen at creation): **real-time** (live,
with a chess clock) or **correspondence** (async, move-when-you-can). A **Kotlin/Ktor server** owns
authoritative game state and validates every move against a **precomputed actor↔movie graph** held in
memory (O(1) set membership — no per-turn external API call). The pure Kotlin `:core` engine is reused
unchanged. First player who can't name a valid connection loses.

> **Architecture, technical decisions, and roadmap** live in the **`bacons-law-architecture`** skill and
> the documents it points to (`docs/DECISIONS.md`, `ROADMAP.md`, `docs/CASE_STUDY.md`) — consult it when
> reasoning about how the system is built or what to build next. This file holds the **always-on
> operating rules**: repository layout, build/test commands, conventions, and the architecture
> boundaries below. `ROADMAP.md` is the single source for current phase and status.
>
> **Prior efforts preserved as reference, not maintained** — do not modify unless explicitly asked: the
> Kotlin/Compose Android client (`:app`) and the Python/FastAPI showcase (branch
> `fullstack-py-ts-rewrite`, tag `python-fastapi-showcase`, docs under
> [docs/python/](docs/python/README.md)).

---

## Repository layout

The repo root is intentionally **stack-agnostic** — it holds shared docs and meta only. Each
implementation/component is a **self-contained project in its own top-level directory** with its own
toolchain. Adding a new (polyglot) experiment is *adding a directory*, not restructuring the root.

Gradle commands run from `kotlin/` (that's where `settings.gradle.kts` and the wrapper live). Gradle
module notation (`:core`, `:backend`, `:app`) is unchanged — it's relative to the `kotlin/` project.

### `:core` — the pure engine (reused)

The game state machine: `GameState`, `Move` (`Move.Actor` / `Move.Movie`), `playMove`, `forfeit`. It
has no platform or I/O dependencies and **must stay that way**. `Move.Movie.castIds: Set<Int>` is the
validation contract; the engine checks `castIds.contains(...)` and makes no network calls. The
authoritative engine spec is [docs/GAME_SPEC_V2.md](docs/GAME_SPEC_V2.md).

### `:backend` → the game server

Currently a thin TMDB proxy (movie/person search, credits); being rebuilt into the graph-backed
authoritative session server. It depends on `:core`, never the reverse. For the target session-layer
design (durable store, transport-agnostic move pipeline, real-time/correspondence modes, identity), see
the **`bacons-law-architecture`** skill.

### `etl/` — the offline graph build (Python)

A separate Python toolchain (`uv`/`ruff`) that runs offline, not in the request path. It produces the
versioned artifact the server loads. Python is the right tool for the data-wrangling here; the
polyglot split is allowed across the offline/online seam only (see ADR 011).

### `:app` — Android client (secondary)

Compose UI. Built for the old pass-the-phone model; will be modernized into a thin multi-device client
that renders server-pushed state (or replaced by a new web client — decided at Phase 4). It depends on
`:core` and never holds data-source credentials.

---

## Environment Setup

**There is no TMDB key in the new architecture** — validation data comes from CC0 Wikidata, built
offline. Do not reintroduce a per-turn movie-API dependency.

- **ETL (Phase 1+):** runs offline; its Wikidata access needs no secret. Output is a versioned graph
  artifact consumed by the server.
- **Server:** needs `DATABASE_URL` and `REDIS_URL` — see
  [kotlin/backend/CLAUDE.md](kotlin/backend/CLAUDE.md).

---

## Build & Test Commands

Gradle commands run from `kotlin/`; the ETL runs from `etl/`. No build tooling runs from the repo root.

`:core:test` is the fast feedback loop for game logic.

---

## Deployment

Hosting is **Fly.io, not Cloud Run** — persistent WebSocket connections (real-time mode) and the
in-process graph are incompatible with scale-to-zero / multi-instance autoscaling. The server runs as a
**single long-lived instance by design**. Concurrent moves are serialized by **optimistic concurrency
(version/CAS) on the durable store** — the authoritative mechanism across both modes (an in-process
per-room `Mutex` may remain only as a same-instance fast-path). The graph artifact is bundled with /
loaded by the server at boot. Postgres (authoritative game state) and Redis (presence/cache) run
colocated on Fly. See [ROADMAP.md](ROADMAP.md) Phase 5.

---

## Code Conventions

- **Commits:** Conventional commit format — `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- **Kotlin style:** follow existing style; prefer pure functions and immutable data in `:core`.
- **Build versions:** declared in `gradle/libs.versions.toml`. Don't hardcode version strings.
- **Python (etl/):** keep it self-contained and offline.

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

**The durable store is authoritative for game state.** The serialized `:core` `GameState` (plus mode,
time-control, players, and clock/deadline state) lives in Postgres per game — it must survive restarts
and span days for correspondence play (ADR 012). **Redis is presence + pub/sub broadcast + hot-game
cache, never the source of truth** (do not put authoritative state behind a TTL). Multi-device (many
clients on one game) does not require multiple server instances; horizontal scaling is a deferred pair
(Redis-coordinated locking + Pub/Sub broadcast — ADR 008).

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
| [docs/DECISIONS.md](docs/DECISIONS.md) | ADR log; 008–013 cover the current direction (012–013: async modes + identity) |
| [ROADMAP.md](ROADMAP.md) | Phased plan, sequencing, and current status (single source for phase/status) |
| `bacons-law-architecture` skill | System architecture, decisions, and roadmap orientation (points to the docs above) |
| `movie-actor-chain-game` skill | Domain rules, vocabulary, and state machine (implementation-agnostic) |
| [docs/GAME_SPEC.md](docs/GAME_SPEC.md) | Retained for product intent / out-of-scope (engine rules superseded by V2) |
| [docs/python/](docs/python/README.md) | Archived Python/FastAPI showcase docs |
