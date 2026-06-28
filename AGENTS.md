# Agents Guide — Bacon's Law (Python/TypeScript)

A trivia game based on "Six Degrees of Kevin Bacon." Two players take turns naming movies and actors
to build a chain of connections; every move is validated in real time against TMDB data. First player
who can't name a valid connection loses.

**Target model: remote, real-time, two-device multiplayer.** Two players on **separate devices**
connect to the same room over the network. A FastAPI backend owns authoritative game state; clients
submit move *intents* over a WebSocket and render the state the server pushes back. There is no
local-only / pass-the-phone mode in this project — multi-device is the core requirement, not a
deferred phase. Turns are sequential as a game rule, but the server treats turn-validation and
state-mutation as a single atomic step (a near-simultaneous out-of-turn message must be rejected, not
raced).

> **This branch (`fullstack-py-ts-rewrite`) is the Python/TypeScript project.** A separate
> Kotlin/Android implementation of the same game is a parallel showcase living on `main`; its docs
> are archived under [`docs/kotlin/`](docs/kotlin/). Nothing on this branch depends on it.

**Current status:** Phase 3 (Multiplayer Session Layer) — building the Redis-backed room store and
WebSocket session handling. The pure game engine (Phase 1) and TMDB REST proxy (Phase 2) are built.
See [docs/PYTHON_TS_REWRITE_PLAN.md](docs/PYTHON_TS_REWRITE_PLAN.md) for the source-of-truth plan and
[ROADMAP.md](ROADMAP.md) for the phase overview.

---

## Module Map

```
bacons-law/
├── server/                  # Python — FastAPI backend (the authoritative game server)
│   ├── app/
│   │   ├── engine/          # Pure game engine — GameState, Move, play_move, forfeit. No I/O.
│   │   ├── api/             # REST routes — TMDB proxy (search, credits), POST /rooms, history
│   │   ├── ws/              # WebSocket room/session handling — join, move, forfeit, broadcast
│   │   ├── store/           # Redis (live room state) + Postgres (game history) access
│   │   ├── models/          # Pydantic models (request/response, TMDB) — barrel-exported
│   │   ├── util/            # Shared helpers
│   │   ├── deps.py          # FastAPI dependency providers (DI)
│   │   └── main.py          # App factory, router wiring, lifespan
│   └── tests/               # pytest suite (asyncio_mode=auto)
├── packages/
│   └── game-client/         # Shared TypeScript — game/session types, REST + WS client, hooks.
│                            #   No UI-framework dependency; structured so a future React Native
│                            #   app can reuse it. (RN itself is out of scope for this initiative.)
└── web/                     # React + Vite + TS app — NOT YET CREATED (Phase 4). Consumes game-client.
```

### `server/app/engine` — the pure core

The game state machine: `ActorMove`, `MovieMove`, `Move`, `InProgress`, `GameOver`, `GameState`,
`play_move`, `forfeit`. **It performs no I/O** — no TMDB, Redis, Postgres, or network calls. All data
needed for validation (a movie's `cast_ids`) must be populated by the caller before a move reaches
`play_move`. This purity is an architectural boundary (see below). The engine is the Python port of
the Kotlin `:core` module; [docs/GAME_SPEC_V2.md](docs/GAME_SPEC_V2.md) is its authoritative spec.

### `server/app/{api,ws,store}` — the session layer

- **`api/`** — stateless REST: the TMDB proxy (`/movies/search`, `/people/search`,
  `/movies/{id}/credits`), plus `POST /rooms` (create room) and history read endpoints.
- **`ws/`** — one WebSocket channel per room (`/ws/rooms/{code}`): join, submit move (delegates to
  the engine), forfeit, reconnect, and state broadcast to all connected clients in the room.
- **`store/`** — **Redis** holds live `GameState` per room, keyed by room code, TTL'd so abandoned
  rooms expire. **Postgres** (SQLAlchemy + Alembic) is written exactly once per game, when a room
  reaches `GameOver`, for history/list/detail views. Redis is authoritative during play; Postgres is
  a one-shot archival write at the end — no in-flight dual-write to reconcile.

### `packages/game-client` — shared client logic

REST calls, WebSocket client, state types, and reconnect handling live here, framework-agnostic, so
`web/` (and a hypothetical React Native app) contain UI only. The boundary exists from day one even
though `web/` doesn't yet — extracting it after the fact would be a real refactor.

---

## Environment Setup

TMDB API access requires a key that is **never embedded in any client bundle**. The key belongs to
`server/` only.

**Production:** stored as a Fly.io secret (`fly secrets set TMDB_API_KEY=…`), injected as an env var.

**Local development:** set it in the environment for the backend:

```
export TMDB_API_KEY=your_key_here
```

Get a free key at https://developer.themoviedb.org/docs/getting-started

Do not commit the key. The web client never reads it — all TMDB access goes through `server/`.

---

## Build & Test Commands

### Backend (`server/`) — requires Python 3.12+ and [uv](https://docs.astral.sh/uv/)

| Task | Command (run from `server/`) |
|------|------|
| Install deps | `uv sync` |
| Run the dev server | `uv run uvicorn app.main:app --reload` |
| Lint | `uv run ruff check .` |
| Type-check | `uv run mypy app` |
| Tests | `uv run pytest` |
| Full local check | `./scripts/check.sh` (ruff + mypy + pytest) |

### Workspace (TypeScript) — requires [pnpm](https://pnpm.io/)

| Task | Command (run from repo root) |
|------|------|
| Install deps | `pnpm install` |
| Type-check the shared client | `pnpm --filter @bacons-law/game-client typecheck` |

**CI:** `.github/workflows/ci.yml` runs `uv sync --frozen`, ruff, mypy, and pytest for `server/` on
pull requests targeting `fullstack-py-ts-rewrite`.

---

## Deployment

Hosting is **Fly.io, not Cloud Run** — persistent WebSocket connections and in-process session state
are fundamentally incompatible with scale-to-zero / multi-instance autoscaling. Fly.io runs
long-lived processes and offers colocated Redis (Upstash) and Postgres. The backend runs as a single
long-lived instance **by design**; the per-room `asyncio.Lock` is authoritative for serializing room
mutations. See [docs/PHASE_5_PLAN.md](docs/PHASE_5_PLAN.md) for the full deploy walkthrough.

- App + Redis + Postgres on Fly.io; `TMDB_API_KEY`, `REDIS_URL`, `DATABASE_URL` injected via
  `fly secrets`.
- Web build deployed to a static host (Vercel/Netlify — decided at Phase 5).

---

## Code Conventions

- **Python:** `ruff` (line length 100; rules `E`, `F`, `I`) and `mypy --strict` are the gate. Prefer
  pure functions and immutable data in `engine/`. Pydantic models use a camelCase alias generator for
  the wire format.
- **Package barrels:** a **cross-package consumer imports from the package barrel**
  (`from app.models import X`); a module imports a **sibling within its own package directly**
  (`from app.models.tmdb import X` only inside `app/models/`). Convention, enforced by review — see
  [ADR 008](docs/DECISIONS.md#008-package-barrel-imports-are-a-convention-enforced-by-review--not-tooling).
- **Commits:** Conventional commit format — `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`.
- **Dependencies:** managed by `uv` (Python) and `pnpm` workspaces (TS). Don't hand-edit lockfiles.

---

## Architecture Boundaries

**Keep `engine/` pure.** It must not import from `app.store`, `app.ws`, `app.api`, or any I/O
library. The engine receives moves and returns new state — nothing else. This is what lets it be
tested in isolation against [GAME_SPEC_V2.md](docs/GAME_SPEC_V2.md) and shared with the client.

**TMDB credentials stay server-side.** All TMDB calls are made by `server/`. No client (web, future
RN) ever holds a TMDB key.

**`cast_ids` is the validation contract.** A `MovieMove` carries a `set[int]` of TMDB cast member
IDs. The caller (session layer) fetches these via the TMDB proxy and populates them before passing a
move to `play_move`. The engine makes no network calls.

**Redis is authoritative during play; Postgres is archival.** Live `GameState` lives only in Redis
while a game is in progress. Postgres is written once, at `GameOver`. Never read game state from
Postgres during an active game.

**Identity is a room-scoped opaque token.** No accounts. Creating or joining a room issues a
server-generated token tied to that player-in-that-room, returned to the client and stored
client-side. The token is the capability required to reconnect and resume — it is **never** broadcast
to other clients (it lives server-side in Redis; the state projection sent to clients is token-free).
Lost token = lost identity in that room; no recovery flow in v1.

---

## What to Avoid

- **Do not put a TMDB key in any client bundle** — web or future RN. All TMDB access goes through
  `server/`.
- **Do not add I/O to `engine/`** — it must remain pure (no Redis, Postgres, TMDB, or network).
- **Do not broadcast a player's token** to other clients — it is an auth capability, not display
  data.
- **Do not bypass repeat detection** — `play_move` rejects moves that reuse an actor or movie already
  in the chain. This is a game rule (R5), not a bug.
- **Do not add out-of-scope mechanics** — time limits, passes, challenges, scoring, turn timers, AFK
  auto-forfeit, and accounts are explicitly deferred. See
  [GAME_SPEC_V2.md](docs/GAME_SPEC_V2.md) and the "out of scope" section of
  [PYTHON_TS_REWRITE_PLAN.md](docs/PYTHON_TS_REWRITE_PLAN.md).
- **Do not use TV shows or documentaries** — TMDB is queried for movies only.

---

## Key Documents

| Document | Purpose |
|----------|---------|
| [docs/PYTHON_TS_REWRITE_PLAN.md](docs/PYTHON_TS_REWRITE_PLAN.md) | **Source of truth** for this initiative — architecture, tech stack, phased plan, decisions |
| [docs/GAME_SPEC_V2.md](docs/GAME_SPEC_V2.md) | Authoritative spec for the pure game engine (rules + test cases) |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Rewrite-era ADR log (008+). Kotlin-era ADRs 001–007 archived at [docs/kotlin/](docs/kotlin/DECISIONS.md) |
| [ROADMAP.md](ROADMAP.md) | Phase overview (0–5) |
| [docs/PHASE_*_PLAN.md](docs/) | Detailed per-phase implementation plans |
| [docs/kotlin/](docs/kotlin/) | Archived docs for the parallel Kotlin/Android showcase on `main` |
