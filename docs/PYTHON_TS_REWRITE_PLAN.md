# Bacon's Law — Python/TypeScript Rewrite Plan

This document is the source of truth for the `fullstack-py-ts-rewrite` initiative. It governs everything built on the `fullstack-py-ts-rewrite` branch.

## Why this exists

The original Bacon's Law project (Kotlin docs archived at [docs/kotlin/ROADMAP.md](kotlin/ROADMAP.md), [docs/kotlin/DECISIONS.md](kotlin/DECISIONS.md), [docs/kotlin/GAME_SPEC.md](kotlin/GAME_SPEC.md); code on `main`) is a Kotlin/Compose fullstack showcase. This initiative is a **parallel showcase, not a replacement** — it rebuilds the same game concept on a Python + TypeScript stack to practice and demonstrate that stack specifically. Both versions are intended to coexist indefinitely as independent portfolio pieces. Nothing here assumes the Kotlin code exists, and nothing in the Kotlin docs should be assumed to apply here except where explicitly referenced.

The game rules themselves are unchanged — [docs/GAME_SPEC_V2.md](GAME_SPEC_V2.md) is the source of truth for what a "valid move" is. What's new in this initiative is the _delivery mechanism_: remote, real-time, two-device multiplayer, where the original was local pass-the-phone.

## Goals

- Practice and demonstrate a Python backend (FastAPI, async, WebSockets, Redis, Postgres) and a TypeScript frontend (React, mobile-responsive).
- Build remote multiplayer from the start — this is not a local-first MVP that grows into multiplayer later, the way the Kotlin project's roadmap was structured. There is no local-only milestone in this plan.
- Structure client-side game/session logic so a future React Native app can reuse it without a rewrite. The React Native app itself is explicitly **not** part of this initiative's scope.
- Optimize for learning and demonstrable breadth (real DB, real cache, real real-time transport, real deployment), not for shipping speed.

## Tech stack

| Layer                                | Choice                                            | Why                                                                                                                 |
| ------------------------------------ | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Backend framework                    | FastAPI                                           | Async-native, built-in WebSocket support, Pydantic validation, OpenAPI docs for free                                |
| Backend tooling                      | `uv`, `ruff`, `mypy`, `pytest` / `pytest-asyncio` | Fast modern toolchain, single dependency manager                                                                    |
| Live session state                   | Redis                                             | Ephemeral per-room game state, keyed by room code, supports reconnect lookups and horizontal scaling                |
| Durable history                      | Postgres (SQLAlchemy + Alembic)                   | Queryable record of completed games — players, full move chain, winner, timestamps                                  |
| Hosting (backend + Redis + Postgres) | Fly.io                                            | Native fit for long-lived WebSocket connections; colocated Redis (Upstash) and Fly Postgres keep infra in one place |
| Frontend framework                   | React + TypeScript + Vite                         | Standard, fast dev loop, mobile-responsive by design intent                                                         |
| Frontend styling                     | Tailwind CSS                                      | Fast to build responsive UI, no custom design system needed for v1                                                  |
| Frontend state                       | React hooks/context                               | App's actual state surface (one active game) doesn't justify Redux or similar                                       |
| Monorepo tooling                     | pnpm workspaces                                   | Lightweight; add Turborepo later only if build times demand it                                                      |
| Realtime transport                   | WebSocket (room/session events)                   | Standard answer for turn-based multiplayer push; see "REST vs. WebSocket split" below                               |
| Stateless data                       | REST (search, credits)                            | No reason to put cacheable, stateless lookups on a stateful connection                                              |

## Architecture

### REST vs. WebSocket split

- **REST** — `GET /movies/search`, `GET /people/search`, `GET /movies/{id}/credits`. Stateless TMDB proxy, same responsibility the Kotlin `:backend` had. Also `POST /rooms` (create room) and `GET /games/{id}` (history detail) live here.
- **WebSocket** — one channel per room (`/ws/rooms/{code}`). Carries: join, leave, submit move, forfeit, state broadcast, reconnect. This is where `GameState` transitions happen.

### Data ownership

- **Redis** is the only place live `GameState` lives while a game is in progress. Keyed by room code. TTL'd so abandoned rooms expire.
- **Postgres** is written to exactly once per game — when a room transitions to `GameOver` (including forfeit) — with the full move chain, players, and timestamps. It is never read from during an active game; it exists for history/list/detail views after the fact.
- There is no dual-write-in-flight problem: Redis is authoritative during play, Postgres is a one-shot archival write at the end. No reconciliation logic needed between them.

### Identity model

- No accounts. Joining or creating a room produces an opaque, server-issued token tied to that player-in-that-room, returned to the client and stored client-side.
- The token (not a username/password) is what's required to reconnect and resume receiving state for that room. Lost token = lost identity in that room; no recovery flow in v1.

### Reconnect scope (v1)

- A client with a valid token can rejoin its room's WebSocket channel and receive a fresh state snapshot.
- No turn timers, no AFK auto-forfeit. If a player simply never returns, the room sits idle until its Redis TTL expires. Out of scope for v1 — candidate fast-follow.

### Repo structure (this branch)

```
bacons-law/  (on fullstack-py-ts-rewrite)
├── server/                  # FastAPI app
│   ├── app/
│   │   ├── engine/          # ported GameState/Move/GameEngine — pure, no I/O
│   │   ├── api/             # REST routes (search, credits, rooms, history)
│   │   ├── ws/              # WebSocket room/session handling
│   │   ├── store/           # Redis (live state) + Postgres (history) access
│   │   └── models/          # Pydantic + SQLAlchemy models
│   └── tests/
├── web/                     # React + Vite + TS app
│   └── src/
├── packages/
│   └── game-client/         # shared TS: game/session types, REST + WS client, hooks — no UI framework dependency where avoidable
└── docs/
    └── PYTHON_TS_REWRITE_PLAN.md   # this file
```

`core/`, `app/`, and `backend/` (the Kotlin modules) are removed from this branch. They remain intact on `main` — nothing here touches that history.

## Phased plan

### Phase 0: Foundation

- Remove Kotlin module directories from this branch.
- Stand up `server/` — FastAPI skeleton, `uv` project, `ruff`/`mypy` config, `pytest` wired, health check endpoint.
- Stand up `web/` — Vite + React + TS, Tailwind configured, pnpm workspace root.
- Stand up `packages/game-client/` as an empty workspace package, wired into `web/`.
- GitHub Actions: lint + test for both `server/` and the TS workspace, on PRs targeting this branch.

**Done when:** empty-but-wired apps build, lint, and test green in CI.

### Phase 1: Engine port

- Port `GameState`, `Move`, `GameEngine` from Kotlin `:core` to Python as pure, dependency-free logic (`server/app/engine/`).
- Port the Kotlin `GameEngineTest` cases to `pytest` — they are the spec to satisfy, not a reference to improve on.
- No network, no Redis, no FastAPI involvement yet.

**Done when:** ported test suite passes, covering valid moves, invalid connections, repeats, and forfeit — same cases as `core/src/test/kotlin/me/zwsmith/core/GameEngineTest.kt`.

### Phase 2: TMDB REST proxy

- `GET /movies/search`, `GET /people/search`, `GET /movies/{id}/credits` — same response contract shape as the old Kotlin `:backend`.
- TMDB key via Fly secrets, never in any client bundle (same invariant as the original project).

**Done when:** all three endpoints work against real TMDB data and have integration tests with a mocked TMDB client.

### Phase 3: Multiplayer session layer

- `POST /rooms` creates a room, returns room code + creator token.
- WebSocket `/ws/rooms/{code}`: join (with display name), submit move (delegates to the Phase 1 engine), forfeit, broadcast resulting state to all connected clients in the room.
- Redis-backed `GameState` per room, TTL'd.
- Reconnect: existing token + room code re-establishes the WebSocket and receives a current snapshot.
- On `GameOver`, write a row to Postgres: room code, players, full move chain, winner, started/ended timestamps. Alembic migration for the schema.

**Done when:** two separate WebSocket clients (e.g. two browser tabs) can complete a full game with moves validated server-side, and the completed game shows up in Postgres.

### Phase 4: React client

- Screens: create/join room, gameplay (chain display, search, submit, forfeit), game over.
- Mobile-responsive layout as the primary target (this is the explicit design goal, not a stretch case).
- All game/session logic — REST calls, WebSocket client, state types, reconnect handling — lives in `packages/game-client`. `web/` consumes it via hooks; it contains UI only.
- Minimal history views: list of past games, detail view of a single game's chain — reading from the Postgres-backed history endpoint.

**Done when:** two people on two separate devices, on the public internet, can play a full game start to finish through the deployed web app.

### Phase 5: Deploy + playtest

- FastAPI app, Redis, Postgres all running on Fly.io.
- `web/` deployed to a static host (Vercel or Netlify — decide at this phase, not before; no architectural dependency on the choice).
- Manual two-device playtest as the acceptance test for the whole initiative.

**Done when:** the Phase 4 "done when" criterion is met against the deployed (not local) stack.

### Explicitly future / out of scope

- React Native app. `packages/game-client` is built to make this cheap later, but no RN code is written in this initiative.
- Turn timers, AFK auto-forfeit, reconnect grace windows beyond "token still works."
- Accounts, login, or any persistent identity beyond a room-scoped token.
- Multi-instance backend scaling validation (Redis already supports it architecturally, but proving it under load is not a goal here).
- Game mechanic changes — out-of-scope mechanics from the archived [docs/kotlin/GAME_SPEC.md](kotlin/GAME_SPEC.md#explicitly-out-of-scope-mvp) (time limits, passes, scoring, etc.) remain out of scope here too.

## Decisions

Lightweight ADR-style log, in the spirit of [docs/DECISIONS.md](DECISIONS.md) but scoped to this initiative.

---

**This is a parallel showcase, not a replacement.** The Kotlin project and this one demonstrate different stacks and are free to diverge in structure, naming, and even scope. Neither blocks or depends on the other. `main` is untouched by this work until/unless a future decision merges it.

---

**Realtime transport is WebSocket, not SSE or polling.** Turn-based multiplayer needs bidirectional push (move submission, state broadcast) and WebSocket is the standard tool for it — also the more valuable thing to show in a portfolio context. Consequence: hosting must support long-lived connections, which ruled out naive serverless/scale-to-zero deployment.

---

**Hosting is Fly.io, not Cloud Run.** Cloud Run's scale-to-zero and multi-instance autoscaling actively fight persistent WebSocket connections and in-memory state. Fly.io is built around long-lived processes and offers colocated Redis/Postgres, avoiding the workaround infra (min-instances pinning, external state) Cloud Run would need to do the same job.

---

**Redis for live state, Postgres for history — not one store doing both.** Redis is the right tool for fast, ephemeral, key-addressable session state but is a poor fit for durable, queryable records. Postgres is the inverse. Using both means each store does the job it's actually good at, at the cost of running two stateful services instead of one. Given the goal is demonstrating breadth, that cost is acceptable here.

---

**No accounts — room-scoped opaque tokens.** Matches the original project's precedent of deferring real auth until something actually requires it. A signed token (JWT) was considered and rejected: Redis already holds the authoritative state server-side, so signature verification adds complexity with no corresponding benefit.

---

**Basic reconnect only, no AFK handling, in v1.** A token-based rejoin is cheap to build and prevents the most common failure mode (phone lock, accidental tab close) from being unrecoverable. Turn timers and auto-forfeit are real design work (what's a fair timeout? what UI communicates it?) that's better scoped once the core loop is proven, not before.

---

**`packages/game-client` exists from day one, even though React Native doesn't.** Extracting shared client logic after the fact, once `web/` has organically coupled game logic into components, is more expensive than starting with the boundary in place. The cost of the boundary now is low (it's just where the code lives); the cost of retrofitting it later is a real refactor.
