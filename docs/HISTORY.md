# Project History

Two prior efforts preceded the current direction. Neither is maintained, and **neither should be
followed as guidance** — both were built on a per-turn movie-API call, the architecture
[ADR 009](DECISIONS.md) exists to remove. They are recorded here so their code can be found and their
reasoning is not mistaken for current direction.

The detailed plans for both were deleted once they stopped describing the tree. Recover any of them
with `git show ad441ae:docs/archive/<path>` — see the file list at the bottom.

## 1. The Kotlin/Compose pass-the-phone MVP (2026-03-19 → 2026-04-03)

The original build: a **single-device, two-player Android game**. Both players shared one phone and
passed it back and forth; a Kotlin/Ktor backend proxied TMDB so the API key never shipped in the
client binary; `:core` held the pure engine and `GameViewModel` held game state.

It reached a playable MVP and was then set aside. Its reasoning survives as **ADRs 001–007**, each
carrying a supersede marker where it no longer holds. `:app` and `:backend` are still in the tree as
reference; see their `CLAUDE.md` files.

## 2. The Python/FastAPI multi-device showcase (2026-06-17 → 2026-06-29)

A parallel rebuild on FastAPI with async WebSockets, a durable store and a cache, and a
React/TypeScript client. (The specific storage products it used are omitted deliberately — persistence
is being replanned from requirements, and this document is not a source of candidates.)
Its own plan was explicit that it was **a parallel showcase, not a replacement** — a deliberate
learning exercise in that stack, structured as six phases (foundation, engine, TMDB proxy, multiplayer
session layer, web client, deploy). It got as far as the session layer.

**The code is not in the trunk.** It lives on branch `fullstack-py-ts-rewrite`, tagged
`python-fastapi-showcase`:

```sh
git checkout python-fastapi-showcase
```

## 3. The pivot (2026-06-29)

ADRs 008–011 landed together and superseded both efforts at once. The finding that organized
everything since: **validating a move by calling TMDB on every turn was the wrong architecture** — it
put a third-party network hop in the hot path of the one operation the game does. Both prior builds
had it.

The fix was to precompute the actor↔movie relationship offline into a graph the server holds in
memory, which is what `etl/` now builds. That analysis is [CASE_STUDY.md](investigations/000-system-design-case-study.md) §2 and §6;
the decisions are ADRs 008–011, extended by 012–013 (async modes, identity) on 2026-07-06.

The showcase's own ADR log (one entry, on Python package barrel imports) went with it.

## What survived

| From the archive | Where it lives now |
|---|---|
| Pivot reasoning, validation-as-the-real-constraint | [CASE_STUDY.md](investigations/000-system-design-case-study.md) |
| Every decision worth keeping | [DECISIONS.md](DECISIONS.md), ADRs 001–013 |
| Engine rules (was `GAME_SPEC.md` / `GAME_SPEC_V2.md`) | [ENGINE_CONFORMANCE.md](ENGINE_CONFORMANCE.md) — the spec of record |
| Hosting analysis (Fly.io over Cloud Run) | [ADR 011](DECISIONS.md), [AGENTS.md](../AGENTS.md) |

The phased roadmaps did **not** survive and were not replaced. There is no roadmap document; don't
infer phase or status from anything in the tree.

## Deleted files

At `ad441ae`, under `docs/archive/`: `GAME_REPOSITORY_REFACTOR.md`, `IMPLEMENTATION_PLAN.md`, and
`python/` (`README.md`, `DECISIONS.md`, `PYTHON_TS_REWRITE_PLAN.md`, `PHASE_0_PLAN.md` through
`PHASE_5_PLAN.md`).
