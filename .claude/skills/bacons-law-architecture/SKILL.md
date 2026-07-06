---
name: bacons-law-architecture
description: System architecture, technical decisions, and roadmap for the Bacon's Law project — the graph-backed Kotlin/Ktor server, Python ETL, real-time + correspondence game modes, durable store, identity model, and deployment/sequencing. Consult this skill whenever working on or reasoning about the backend, server architecture, the data/ETL pipeline, the session/transport layer, persistence, identity, deployment, or what to build next. Trigger it whenever a task touches how the system is built or how the work is sequenced, even when the user never says "architecture" or "roadmap". This is the system-design companion to the movie-actor-chain-game skill (which owns domain rules and is deliberately implementation-agnostic).
---

# Bacon's Law — System Architecture & Roadmap

Orientation for the system design and project direction. This skill is a **map, not the territory** —
the authoritative detail lives in the documents linked below. When they disagree with this summary, the
documents win; update this skill to match rather than duplicating their content here.

## How to use this context

- For **operating rules** an agent must always honor (keep `:core` pure, no per-turn external API call,
  don't split the engine from the graph, durable store is authoritative not Redis, `castIds` is the
  validation contract, build/test commands, code conventions) → **`AGENTS.md`** is the source of truth.
  Those guardrails are intentionally kept in always-loaded context; this skill does not restate them.
- For **why the system is shaped this way and what to build next** → this skill plus the docs below.

## The one load-bearing property

**Validation is co-located with the graph, in-process.** The per-turn connection check is O(1) set
membership (`castIds.contains(...)`) against a precomputed bipartite graph loaded read-only at boot —
no per-turn external API call. This holds **only** while the graph and the validation logic share a
process, so the engine/data seam must never cross a network hop. Everything else is downstream of this.
(CASE_STUDY §2, §6; ADR 009.)

## Current direction in brief

Each bullet is a pointer to its authoritative record — read that for detail, don't rely on this gloss.

- **Data:** a Python ETL (`etl/`) precomputes the graph + entity search index from **CC0 Wikidata**,
  offline, with a top-N cast-depth cap. Loaded into the Kotlin/Ktor server at boot. (ADRs 009, 010, 011.)
- **Engine:** the pure Kotlin `:core` module, reused unchanged — a turn-based state machine, no I/O,
  no concept of wall-clock time. Spec: `docs/GAME_SPEC_V2.md`.
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
Current phase and detailed sequencing: **`ROADMAP.md`** (Phase 3 is split 3a correspondence / 3b
real-time). This skill does not track live status — `ROADMAP.md` does.

## Sources of truth

| Topic | Document |
|-------|----------|
| Technical & product decisions (ADR log) | `docs/DECISIONS.md` — ADRs 008–013 are the current direction |
| Phased plan, sequencing, current status, scope | `ROADMAP.md` |
| System-design reasoning (the "why") | `docs/CASE_STUDY.md` |
| Pure game engine (rules + state machine) | `docs/GAME_SPEC_V2.md` |
| Domain rules & vocabulary (implementation-agnostic) | `movie-actor-chain-game` skill |
| Always-on operating rules & guardrails | `AGENTS.md` |
