# Stage 0 — Scaffolding (answer key)

**Goal:** a self-contained `etl/` project a fresh clone can build from scratch, with the shared
contracts (`config.py`, `models.py`, `paths.py`) every later stage imports.

Guide reference: [../IMPLEMENTATION_GUIDE.md](../IMPLEMENTATION_GUIDE.md) §"Stage 0". Shared types live
in [README.md](./README.md) §"Shared contracts" — this doc covers the *project* setup around them.

---

## 1. `pyproject.toml` (already committed — this is the target state)

```toml
[project]
name = "etl"
version = "0.1.0"
description = "Offline batch pipeline: builds the versioned actor↔movie graph artifact from CC0 Wikidata."
readme = "README.md"
requires-python = ">=3.14"
dependencies = [
    "httpx2>=2.5.0",
]

[dependency-groups]
dev = [
    "pytest>=9.1.1",
    "ruff>=0.15.20",
    "ty>=0.0.56",
]

[build-system]
requires = ["uv_build>=0.11.24,<0.12.0"]
build-backend = "uv_build"

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["F", "E", "I", "UP", "B", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = ["live: hits the real WDQS endpoint; deselected by default"]
```

The only addition vs. what's committed is the `markers` line — it registers the `live` marker used by
the extract smoke test (04-testing) so pytest doesn't warn about an unknown marker.

**Why `httpx2`, and how to import it:** `httpx2` is the maintained continuation of `httpx`. The
dependency string is `httpx2` — leave it. In this venv the package imports as `httpx2` (verified:
`import httpx` fails), so write **`import httpx2 as httpx`** and keep call sites as `httpx.post(...)`.
Don't "reconcile" the dependency down to `httpx`; alias the import.

## 2. Commands you'll actually run

```bash
uv sync                       # create/refresh the locked env from pyproject + uv.lock
uv run python -m etl build    # run the pipeline (Stage 1→3), default config
uv run pytest                 # the fast suite (no network)
uv run pytest -m live         # opt-in: the single live SPARQL smoke test
uv run ruff check             # lint
uv run ruff format            # format
uv run ty check               # typecheck (src + tests)
```

If you're adding a dependency later: `uv add <pkg>` (runtime) / `uv add --dev <pkg>` (dev). The lockfile
is part of the reproducibility guarantee — commit it.

## 3. Final package layout (what you're building toward)

```
etl/
  pyproject.toml
  uv.lock
  README.md
  data/                    # gitignored: raw/ + interim/ caches (created at runtime)
  graph/                   # versioned artifacts, e.g. graph/v1/  (committed or shipped)
  src/etl/
    __init__.py
    __main__.py            # CLI: python -m etl build [flags]        (04-testing)
    config.py              # BuildConfig — frozen, manifest params    (README §Shared contracts)
    paths.py               # directory layout + path helpers          (README §Shared contracts)
    models.py              # Actor, Film, Edge dataclasses            (README §Shared contracts)
    sparql.py              # thin SPARQL-over-HTTP client + URI→QID    (01-extract)
    extract.py             # Stage 1 — fetch, cache, resume           (01-extract)
    transform.py           # Stage 2 — filter, cap, fold (PURE)       (02-transform)
    emit.py                # Stage 3 — invert, index, manifest (PURE) (03-emit)
  tests/
    conftest.py
    fixtures/
    test_transform.py
    test_emit.py
    test_extract.py
```

## 4. `.gitignore` for `etl/`

`data/` is a rebuildable cache — never commit it. `graph/` is the *product*; whether you commit it or
ship it separately is a Phase 2 concern, so leave it tracked for now.

```gitignore
data/
__pycache__/
.pytest_cache/
.ruff_cache/
*.pyc
```

## 5. Create the two shared modules now

Copy `paths.py` and `models.py` verbatim from [README.md](./README.md) §"Shared contracts". They have
no dependencies on the other stages, so building them first means every subsequent `from etl.models
import ...` / `from etl import paths` resolves cleanly and you can unit-test stages in isolation.

`config.py` is already committed and correct — leave it. Note the inline `[extract-time]` /
`[transform-time]` tags in the README copy: they're the D1 decision made visible at the definition site.

---

## Verify Stage 0 in isolation

```bash
uv sync
uv run python -c "from etl import paths, models, config; print(paths.ROOT, paths.raw_path(1994).name)"
# → …/etl films-1994.json
uv run ruff check && uv run ty check
```

If `paths.ROOT` doesn't point at the `etl/` directory, your `parents[2]` index is wrong for where you
put `paths.py` — it must sit at `src/etl/paths.py` (three parents up from the file to reach `etl/`).
