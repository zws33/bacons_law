---
name: bacons-law-architecture
description: System architecture, technical decisions, and build order for the Bacon's Law project — the graph-backed Kotlin/Ktor server, Python ETL, real-time + correspondence game modes, durable store, identity model, and deployment/sequencing. Consult this skill whenever working on or reasoning about the backend, server architecture, the data/ETL pipeline, the session/transport layer, persistence, identity, deployment, or what to build next. Trigger it whenever a task touches how the system is built or how the work is sequenced, even when the user never says "architecture" or "roadmap". This is the system-design companion to the movie-actor-chain-game skill (which owns domain rules and is deliberately implementation-agnostic).
---

# Bacon's Law — System Architecture & Roadmap

Orientation for the system design and project direction. This skill is a **map, not the territory** —
the authoritative detail lives in the documents linked below. When they disagree with this summary, the
documents win; update this skill to match rather than duplicating their content here.

## How to use this context

- For **operating rules** an agent must always honor (keep the engine pure, no per-turn external API
  call, don't split the engine from the graph, durable store is authoritative not Redis, cast QIDs are
  the validation contract, build/test commands, code conventions) → **`AGENTS.md`** is the source of
  truth.
  Those guardrails are intentionally kept in always-loaded context; this skill does not restate them.
- For **why the system is shaped this way and what to build next** → this skill plus the docs below.

## The one load-bearing property

**Validation is co-located with the graph, in-process.** The per-turn connection check is O(1) set
membership (is this cast QID in that movie's set?) against a precomputed bipartite graph loaded read-only at boot —
no per-turn external API call. This holds **only** while the graph and the validation logic share a
process, so the engine/data seam must never cross a network hop. Everything else is downstream of this.
(CASE_STUDY §2, §6; ADR 009.)

## What is settled, and what is not

**`etl/` is the only durable source code and the only fixed contract** — a working pipeline that
builds the graph the engine validates against. Everything below describing the *application* — engine
module, server, persistence, session layer, identity, deployment, and the language they're written in
— is **provisional**. The whole application build-out will be reevaluated in a planning session.

So: read the ADRs for the **reasoning**, which is durable, not as commitments. When a task asks
"should we keep X," the answer is never "because ADR N said so" — it's whether X still follows from
the load-bearing property above and the ETL's contract.

## Current direction in brief

Each bullet is a pointer to its record — read that for detail, don't rely on this gloss.

- **Data:** a Python ETL (`etl/`) precomputes the graph + entity search index from **CC0 Wikidata**,
  offline, with a top-N cast-depth cap. Loaded into the Kotlin/Ktor server at boot. (ADRs 009, 010, 011.)
- **Engine:** a pure turn-based state machine — no I/O, no concept of wall-clock time. Currently the
  Kotlin `:core` module, but that is **provisional**: everything outside `etl/` may change or be
  replaced at the planning session, stack included. Purity is the requirement; `:core` is one
  implementation of it. There is no prose spec; the code and its tests are the spec.
- **Two game modes (chess.com model):** **real-time** (live, chess clock) or **correspondence** (async,
  move-when-you-can, push on your turn), chosen at game creation. Async is a firm requirement. (ADR 012.)
- **Persistence:** a **durable store (Postgres) is authoritative** for game state — the serialized
  `:core` `GameState` plus mode, time-control, players, and clock/deadline state. **Redis is demoted** to
  presence + pub/sub broadcast + hot-game cache, never source of truth. (ADR 012.)
- **Session layer:** one **transport-agnostic move pipeline** (*authenticate → load → validate against
  graph → persist → notify*); HTTP adapter (correspondence) and WebSocket adapter (real-time) feed it.
  Concurrent moves serialize via **optimistic concurrency (version/CAS) on the store**, not an in-process
  `Mutex`. Clocks are session-layer state inside the durable game row, never in `:core`. (ADR 012.)
- **Identity:** **device-anchored persistent Player tokens** for v1 (span games, carry push tokens, back
  a "my games" list); credentialed accounts (email/OAuth, cross-device, recovery) designed-for but
  deferred. Supersedes the old room-scoped-token strategy. (ADR 013.)
- **Deployment:** a single long-lived **Fly.io** instance (not Cloud Run — scale-to-zero is incompatible
  with real-time WebSockets + the in-process graph); Postgres + Redis colocated. (ADR 011, 012.)

## Build order

**Correspondence-first, then real-time as an additive layer.** Correspondence exercises the two hard
foundations (durable persistence + persistent identity) with the fewest moving parts; real-time (WS
transport, presence, pub/sub, the chess-clock subsystem) layers on the proven base. The
transport-agnostic move pipeline is the discipline that makes this additive rather than a rewrite.

**There is no roadmap document right now** — the phased plan was retired pending regeneration in a
planning session. Nothing tracks live status; establish it from the code and `git log` rather than
assuming a phase. The build order above and `docs/DECISIONS.md` are what survive of the sequencing.

## Sources of truth

| Topic | Document |
|-------|----------|
| Technical & product decisions (ADR log) | `docs/DECISIONS.md` — ADRs 008–013 are the current direction |
| System-design reasoning (the "why") | `docs/CASE_STUDY.md` |
| Pure game engine (rules + state machine) | `kotlin/core/.../GameEngine.kt` and its tests — no prose spec |
| Offline graph build | `etl/AGENTS.md` |
| Domain rules & vocabulary (implementation-agnostic) | `movie-actor-chain-game` skill |
| Always-on operating rules & guardrails | `AGENTS.md` |
