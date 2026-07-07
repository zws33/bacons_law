# ETL Answer Keys — index & shared contracts

> **What this folder is.** Detailed, per-stage *answer keys* for building the `etl/` pipeline
> described in [../IMPLEMENTATION_GUIDE.md](../IMPLEMENTATION_GUIDE.md). The guide is the "why" and the
> map; these docs are the "here is one correct, complete implementation" you can fall back to when you
> get stuck **offline, without a coding agent**. Build from the guide first; open the matching answer
> key only when blocked, then close it again.

Each stage doc is self-contained: goal, the exact contracts it consumes/produces, complete reference
code, the pitfalls that will actually bite you, and a **"verify this stage in isolation"** section so
you never have to run the whole pipeline to know a stage works.

| Doc | Stage | Module(s) |
|-----|-------|-----------|
| [00-scaffolding.md](./00-scaffolding.md) | Project skeleton, config, shared types, paths | `pyproject.toml`, `config.py`, `models.py`, `paths.py` |
| [01-extract.md](./01-extract.md) | SPARQL → `data/raw/*.json` (I/O, cached, resumable) | `sparql.py`, `extract.py` |
| [02-transform.md](./02-transform.md) | raw → `data/interim/edges.jsonl` (pure: filter, cap, fold) | `transform.py` |
| [03-emit.md](./03-emit.md) | edges → `graph/<version>/` (pure: invert, index, manifest) | `emit.py` |
| [04-testing-and-verification.md](./04-testing-and-verification.md) | unit tests, CLI wiring, "done when" | `__main__.py`, `tests/` |

---

## Data flow (what moves between stages)

```
Wikidata (SPARQL)          data/raw/                 data/interim/           graph/<version>/
   │ extract (I/O)    →   films-1900.json      →     edges.jsonl        →    manifest.json
   │ per year, cached      films-1901.json           (capped edges,          graph.json
   │ self-describing       …                          deterministic order)
   │
   └─ each raw file wraps its rows in a provenance header (see below)
```

Two data shapes, named once so every stage agrees:

- **Denormalized row** — one per (film, actor) pair, straight out of SPARQL. Flattened + QIDs stripped
  from URIs by `sparql.py`. Carried on disk inside a per-year provenance wrapper.
- **Adjacency maps** — the artifact: `movie → [actors]`, `actor → [movies]`. Built once in `emit`.

---

## Resolved design decisions (the review's open questions, answered)

The high-level guide left six things ambiguous. These answer keys commit to a specific resolution for
each so the code across stages is internally consistent. If you disagree with one, change it *here and
in every stage doc together* — that's the point of pinning them.

### D1 — Filter placement across the cache seam
`min_sitelinks` and `require_enwiki` are applied **in the SPARQL** (extract-time). They are therefore
**baked into `data/raw/`**. To make this safe rather than a silent-staleness trap, **each raw file
records the `min_sitelinks` / `require_enwiki` that produced it**, and `extract` treats a cached file as
valid *only if those params match the current config*. Change the notability floor → the affected years
re-fetch automatically; no stale cache. `min_cast` and `cast_cap` — the dials you actually tune dozens
of times — live in **transform** and never touch the cache. (Alternative not taken: pull at a loose
floor and filter sitelinks in transform. It makes the sitelink dial cache-free at the cost of a bigger
raw cache. Fine to switch to; see 01-extract.md §"Cache validity".)

### D2 — The query is fully templated from config
`render_query(year, config)` interpolates **every** config-derived value — `min_sitelinks`, the enwiki
block (present only when `require_enwiki`), *and* the year — not just the year. No hardcoded `>= 5`.

### D3 — Field names are pinned to the existing `config.py`
Config fields are `from_year` / `to_year` (as already committed). The CLI exposes them as `--year-from`
/ `--year-to` (nicer to type); `__main__.py` maps flag→field. Directory paths do **not** live in
`BuildConfig` (it holds only manifest-worthy params); they live in `paths.py`.

### D4 — `edges.jsonl` has one exact schema
One JSON object per line: `{"movie", "movie_label", "actor", "actor_label"}`. Sitelink counts are
consumed *inside* transform (for the cap ranking) and **deliberately dropped at this seam** — emit
doesn't need them. The `Edge` dataclass mirrors these four fields exactly.

### D5 — Versioning is an explicit flag, writes overwrite
`--version` (default `v1`) names the output directory. Re-running the same version **overwrites** it.
Because emit is deterministic, a re-run produces byte-identical files — which is exactly what the
reproducibility check asserts. No auto-increment (it would fight determinism).

### D6 — `query_date` is a range derived from the raw cache
A pull can span days (it's resumable). Each raw file stamps its own `fetched_at`; the manifest records
the **min and max** across all raw files as `query_date: {"from", "to"}`, plus a separate
`generated_at` for the emit run.

---

## Shared contracts (used by every stage)

Two small modules the guide implied but never placed. Build these in Stage 0; every later stage imports
them. **These are the load-bearing types — if the code below and a stage doc ever disagree, this file
wins.**

### `src/etl/paths.py` — the directory layout, in one place

```python
from pathlib import Path

# This file is etl/src/etl/paths.py → parents[2] is the etl/ project root.
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
GRAPH_DIR = ROOT / "graph"


def raw_path(year: int) -> Path:
    return RAW_DIR / f"films-{year}.json"


def edges_path() -> Path:
    return INTERIM_DIR / "edges.jsonl"


def graph_version_dir(version: str) -> Path:
    return GRAPH_DIR / version
```

### `src/etl/models.py` — the shapes that move between stages

```python
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Actor:
    qid: str
    label: str
    sitelinks: int


@dataclass
class Film:
    qid: str
    label: str
    sitelinks: int
    # actor_qid -> Actor. A dict so duplicate rows across year partitions collapse for free.
    cast: dict[str, Actor] = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    movie: str
    movie_label: str
    actor: str
    actor_label: str
```

### `src/etl/config.py` — already committed; the single source of tunable truth

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class BuildConfig:
    min_sitelinks: int = 5       # notability floor (EXPLORATION: 5 → ~68k films)   [extract-time, D1]
    min_cast: int = 3            # min-cast floor (drops ~25% dead-weight films)     [transform-time]
    cast_cap: int = 15           # top-N by ACTOR sitelink count (not billing order) [transform-time]
    require_enwiki: bool = True  # English-audience recognizability anchor           [extract-time, D1]
    user_agent: str = "bacons-law-etl/0.1 (zach.smith33@gmail.com)"
    endpoint: str = "https://query.wikidata.org/sparql"
    from_year: int = 1900
    to_year: int = 2026
```

Every field here is echoed into `manifest.json` (03-emit.md) — that's what makes a build reproducible
and self-describing.

---

## Conventions used in all reference code

- **Imports are absolute**, rooted at the `etl` package (`from etl.config import BuildConfig`,
  `from etl import paths`), matching the existing `extract.py`.
- **The config parameter is named `config`**, not `cfg` (again, matching the existing code).
- **`httpx2` is the installed package, and in this venv it imports as `httpx2`** — so write
  `import httpx2 as httpx` and keep every call site as `httpx.post(...)`. Don't change the dependency to
  `httpx`; alias the import instead. (Verified against the installed `httpx2==2.5.0`, which ships only a
  top-level `httpx2` module — `import httpx` raises `ModuleNotFoundError`.)
- **Python 3.14 / ruff line-length 100** — modern syntax (`X | None`, `list[dict]`) is fine.
- Stage entry functions are named after their module: `extract(config)`, `transform(config)`,
  `emit(...)`.
