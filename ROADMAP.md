# Bacon's Law Roadmap

## Project Summary

A trivia game based on "Six Degrees of Kevin Bacon." Two players take turns naming movies and actors;
each answer must connect to the previous one (the actor was in that movie, or the movie features that
actor). Every move is validated against [TMDB](https://www.themoviedb.org/) data. First player who
can't name a valid connection loses.

This is the **Python/TypeScript** build: remote, real-time, **two-device** multiplayer with a
server-authoritative FastAPI backend. A separate Kotlin/Android implementation of the same game is a
parallel showcase on `main` (its roadmap is archived at [docs/kotlin/ROADMAP.md](docs/kotlin/ROADMAP.md)).

> **Source of truth:** [docs/PYTHON_TS_REWRITE_PLAN.md](docs/PYTHON_TS_REWRITE_PLAN.md). This file is
> the phase overview; that document governs architecture and scope. Per-phase detail lives in
> [docs/PHASE_0_PLAN.md](docs/PHASE_0_PLAN.md) … [docs/PHASE_5_PLAN.md](docs/PHASE_5_PLAN.md).

**Current phase:** Phase 3 — Multiplayer Session Layer.

See [docs/GAME_SPEC_V2.md](docs/GAME_SPEC_V2.md) for the engine rules and
[docs/DECISIONS.md](docs/DECISIONS.md) for the decision log.

---

## Phase 0: Foundation ✅

**Goal:** Empty-but-wired apps that build, lint, and test green in CI.

- Stand up `server/` — FastAPI skeleton, `uv` project, `ruff`/`mypy`/`pytest` configured, health check.
- Stand up the pnpm workspace and `packages/game-client/` as a wired-in package.
- GitHub Actions: lint + test on PRs targeting `fullstack-py-ts-rewrite`.

---

## Phase 1: Engine Port ✅

**Goal:** The pure game engine, ported and tested.

- Port `GameState`, `Move`, and the engine from Kotlin `:core` to Python (`server/app/engine/`) as
  pure, dependency-free logic — no network, no Redis, no FastAPI.
- Port the Kotlin engine test cases to `pytest`; they are the spec to satisfy. See
  [docs/GAME_SPEC_V2.md](docs/GAME_SPEC_V2.md).

**Done when:** the ported suite passes — valid moves, invalid connections, repeats, forfeit.

---

## Phase 2: TMDB REST Proxy ✅

**Goal:** Stateless TMDB proxy endpoints.

- `GET /movies/search`, `GET /people/search`, `GET /movies/{id}/credits`.
- TMDB key via Fly secrets, never in any client bundle.

**Done when:** all three endpoints work against real TMDB data with integration tests over a mocked
TMDB client.

---

## Phase 3: Multiplayer Session Layer ⬅ current

**Goal:** Two separate WebSocket clients can complete a full game, validated server-side.

- `POST /rooms` creates a room, returns room code + creator token.
- WebSocket `/ws/rooms/{code}`: join (with display name), submit move (delegates to the engine),
  forfeit, broadcast resulting state to all connected clients in the room.
- Redis-backed `GameState` per room, TTL'd. Reconnect via existing token + room code yields a fresh
  state snapshot.
- On `GameOver`, write one Postgres row (room code, players, full move chain, winner, timestamps).
  Alembic migration for the schema.

**Done when:** two browser tabs can play a full game with server-side validation, and the completed
game is persisted to Postgres.

---

## Phase 4: React Client

**Goal:** A real, mobile-responsive web client.

- Screens: create/join room, gameplay (chain display, search, submit, forfeit), game over.
- Mobile-responsive layout is the primary design target.
- All game/session logic (REST, WebSocket, state types, reconnect) lives in
  `packages/game-client`; `web/` consumes it via hooks and contains UI only.
- Minimal history views — list of past games, detail of a single game's chain — from the
  Postgres-backed history endpoint.

**Done when:** two people on two separate devices, on the public internet, can play a full game
through the deployed web app.

---

## Phase 5: Deploy + Playtest

**Goal:** The whole stack running on real infrastructure.

- FastAPI app, Redis, and Postgres on Fly.io (long-lived process, no scale-to-zero — required for
  persistent WebSocket connections). `web/` on a static host.
- Manual two-device playtest as the acceptance test for the initiative.

**Done when:** the Phase 4 "done when" is met against the deployed (not local) stack.

---

## Explicitly out of scope

React Native app (the shared `game-client` makes it cheap later, but no RN code here); turn timers /
AFK auto-forfeit; accounts or persistent identity beyond a room-scoped token; multi-instance scaling
validation; and the deferred game mechanics (time limits, passes, scoring) from the game spec.
