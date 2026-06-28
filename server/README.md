# Bacon's Law — Backend

The authoritative game server for Bacon's Law: a FastAPI service that proxies TMDB, runs the pure
game engine, and (Phase 3+) owns multiplayer room state over WebSockets. For the project overview see
the [root README](../README.md); for architecture and scope see
[docs/PYTHON_TS_REWRITE_PLAN.md](../docs/PYTHON_TS_REWRITE_PLAN.md) and the
[agents guide](../AGENTS.md).

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- A [TMDB API key](https://developer.themoviedb.org/docs/getting-started)

## Setup

```bash
uv sync
export TMDB_API_KEY=your_key_here   # never commit this; injected via Fly secrets in production
uv run uvicorn app.main:app --reload
```

The server starts on http://127.0.0.1:8000. Interactive API docs are at `/docs`.

## Commands

| Task | Command |
|------|---------|
| Install deps | `uv sync` |
| Dev server (reload) | `uv run uvicorn app.main:app --reload` |
| Lint | `uv run ruff check .` |
| Type-check | `uv run mypy app` |
| Tests | `uv run pytest` |
| Full check (lint + types + tests) | `./scripts/check.sh` |

CI runs the full check on pull requests targeting `fullstack-py-ts-rewrite`
(`.github/workflows/ci.yml`).

## Layout

```
app/
├── engine/   # Pure game engine — no I/O. Spec: docs/GAME_SPEC_V2.md
├── api/      # REST routes — TMDB proxy, POST /rooms, history
├── ws/       # WebSocket room/session handling
├── store/    # Redis (live state) + Postgres (history)
├── models/   # Pydantic models (barrel-exported via app.models)
├── util/     # Shared helpers
├── deps.py   # FastAPI dependency providers
└── main.py   # App factory + lifespan
tests/        # pytest (asyncio_mode=auto)
```

## Conventions

- `ruff` (line length 100; `E`, `F`, `I`) and `mypy --strict` are the gate.
- Keep `engine/` pure — no Redis, Postgres, TMDB, or network imports.
- Cross-package imports go through the package barrel (`from app.models import X`); intra-package
  imports may reference siblings directly. See
  [ADR 008](../docs/DECISIONS.md#008-package-barrel-imports-are-a-convention-enforced-by-review--not-tooling).
- The TMDB key lives only in this service — never in any client bundle.
