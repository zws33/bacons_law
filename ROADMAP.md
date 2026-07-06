# Bacon's Law Roadmap

## Project Summary

A real-time trivia game based on "Six Degrees of Kevin Bacon." Two players on **separate devices**
take turns naming movies and actors; each answer must connect to the previous one — the actor must
have appeared in that movie, or the movie must feature that actor. A Kotlin/Ktor server owns
authoritative game state and validates every move against a precomputed actor↔movie graph. First
player who can't name a valid connection loses.

**Architecture in one line:** a Python ETL precomputes a bipartite movie↔actor graph from CC0
Wikidata data; a Kotlin/Ktor server loads it **read-only, in-process** and validates moves with an
O(1) set-membership check — no per-turn external API call. The pure game engine is the existing
Kotlin `:core` module, reused unchanged.

**Current state:** Pivoting to this direction. The existing Kotlin `:core` engine and Ktor
`:backend` are the starting point — `:core` is reused as-is; `:backend` is rebuilt from a TMDB proxy
into the graph-backed session server. Two prior efforts are preserved as reference, not maintained:
the Kotlin/Compose Android client (`:app`, on this history) and the Python/FastAPI showcase (branch
`fullstack-py-ts-rewrite`, tag `python-fastapi-showcase`, docs archived under
[docs/python/](docs/python/README.md)).

See [docs/GAME_SPEC_V2.md](docs/GAME_SPEC_V2.md) for the engine spec, [docs/CASE_STUDY.md](docs/CASE_STUDY.md)
for the system-design reasoning behind this direction, and [docs/DECISIONS.md](docs/DECISIONS.md) for
the decision log.

> The architecture rests on one property: **validation is co-located with the graph, in-process.**
> The O(1) check holds only while the graph and the validation logic share a process — so the
> engine/data seam must never cross a network hop (see [CASE_STUDY](docs/CASE_STUDY.md) §2, §6 and
> [ADR 009](docs/DECISIONS.md)).

---

## Phase 0: Pivot & reorganization

**Goal:** The trunk reflects the new direction, with prior work preserved and discoverable.

- [ ] Promote stack-agnostic docs to the trunk (CASE_STUDY, GAME_SPEC_V2, game-rules skill).
- [ ] Archive the Python/FastAPI planning docs under `docs/python/`; tag the code
      (`python-fastapi-showcase`).
- [ ] Reconcile the decision log (multi-device, offline validation, Wikidata, Kotlin/Ktor + Fly.io)
      and replace this roadmap.

**Done when:** the trunk builds green, the Python work is tagged + archived, and the docs describe
the Kotlin-server + Python-ETL + Wikidata direction coherently.

---

## Phase 1: ETL → graph artifact (Python)

**Goal:** A reproducible offline pipeline that produces the data the server validates against.

- [ ] Pull movie↔cast relationships from Wikidata (SPARQL / dumps), CC0.
- [ ] Apply a cast-depth cap (top-N billed) — gameplay, policy, and scale lever in one
      ([CASE_STUDY](docs/CASE_STUDY.md) §3).
- [ ] Emit a **versioned artifact**: the bipartite graph (`movie_id → set(actor_id)`,
      `actor_id → set(movie_id)`) plus an entity search index for typeahead.
- [ ] Separate toolchain (`etl/`, `uv`/`ruff`) — no coupling to the Gradle project.

**Done when:** a documented offline run produces a loadable, versioned artifact from scratch.

---

## Phase 2: Engine + graph loading (Kotlin)

**Goal:** The server validates moves from the loaded graph with zero external calls.

- [ ] Reuse `:core` as-is (already pure; `Move.Movie.castIds: Set<Int>` is the validation contract).
- [ ] Server-side graph loader: read the Phase 1 artifact into memory at boot, read-only.
- [ ] Wire validation: populate `castIds` from the in-memory graph; the engine is unchanged.

**Done when:** the server accepts/rejects moves correctly against the loaded graph, with no network
call in the validation path.

---

## Phase 3: Session layer (Ktor) — correspondence-first

**Goal:** Two players complete a full game against durable, server-authoritative state — async
(correspondence) first, real-time layered on after. See [ADR 012](docs/DECISIONS.md) /
[ADR 013](docs/DECISIONS.md).

**3a — durable foundation + correspondence (async):**
- [ ] Device-anchored persistent **Player** identity ([ADR 013](docs/DECISIONS.md)); a "my games" list.
- [ ] Durable **Game** store (Postgres) as source of truth: mode, time-control, both players, the
      serialized `:core` `GameState`, clock/deadline state, status, timestamps.
- [ ] `POST /games` creates a game (mode + time-control), returns a room code = challenge-a-friend link.
- [ ] Transport-agnostic move pipeline — *authenticate → load → validate against graph → persist →
      notify* — with an HTTP move-submission + poll adapter. Serialize with optimistic concurrency
      (version/CAS) on the store, not an in-process `Mutex`.
- [ ] Correspondence per-move deadline (timestamp, lazy/swept); protocol errors (to the offender) stay
      distinct from game events (invalid move → game over).

**3b — real-time layer (additive):**
- [ ] WebSocket `/ws/games/{code}` adapter into the same pipeline; presence + Redis pub/sub broadcast.
- [ ] Real-time chess-clock subsystem (server-authoritative, survives disconnects) → terminal
      "out of time → loss" injected through the engine.
- [ ] Redis as presence + broadcast + hot-game cache (not source of truth).

**Done when:** two players finish a correspondence game against the durable store (3a), then two
WebSocket clients finish a real-time game with clocks (3b).

---

## Phase 4: Search + client

**Goal:** A real, playable two-device experience. (Clients are a secondary learning goal.)

- [ ] Typeahead/search endpoint served from the Phase 1 entity index (resolves names → entity IDs).
- [ ] A client: modernize `:app` into a multi-device client, or build a new web client — decided at
      this phase.
- [ ] Client holds no game logic it doesn't need; it renders server-pushed state.

**Done when:** two people on two separate devices play a full game through the client.

---

## Phase 5: Deploy + playtest

**Goal:** The whole stack running on real infrastructure.

- [ ] Kotlin/Ktor server + Redis on **Fly.io** — a single long-lived instance (no scale-to-zero;
      required for persistent WebSockets and the in-process graph).
- [ ] Graph artifact bundled with / loaded by the deployed server at boot.
- [ ] Secrets via `fly secrets` (`REDIS_URL`; no TMDB key — there is none).
- [ ] Manual two-device playtest as the acceptance test.

**Done when:** the Phase 4 "done when" is met against the deployed (not local) stack.

---

## Explicitly out of scope

Full credentialed accounts (email/OAuth, cross-device, recovery — v1 identity is a device-anchored
persistent token, [ADR 013](docs/DECISIONS.md)); open matchmaking pools (v1 is challenge-a-friend by
room code); multi-instance horizontal scaling (Redis-coordinated locking + Pub/Sub — a deferred pair,
see [ADR 008](docs/DECISIONS.md)); TMDB image assets; and the deferred game mechanics (passes, scoring)
from [GAME_SPEC.md](docs/GAME_SPEC.md).

> Time controls (real-time chess clock + correspondence per-move deadline), persistent identity, and
> durable game-state persistence are **in scope** as of [ADR 012](docs/DECISIONS.md) /
> [ADR 013](docs/DECISIONS.md) — the chess.com-style real-time/correspondence mode split.
