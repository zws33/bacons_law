# Stage 4 — CLI, tests & verification (answer key)

Two jobs: wire the stages into a `python -m etl build` CLI, and prove the whole thing works. Guide
reference: [../IMPLEMENTATION_GUIDE.md](../IMPLEMENTATION_GUIDE.md) §"Testing strategy" +
§"Verification".

---

## `src/etl/__main__.py` — the CLI

Flags map to config fields (D3): CLI `--year-from` → field `from_year`, etc. Any flag left off falls
back to the `BuildConfig` default. `dataclasses.replace` applies only the overrides that were passed.

```python
import argparse
from dataclasses import replace

from etl import emit, extract, transform
from etl.config import BuildConfig


def _config_from_args(args: argparse.Namespace) -> BuildConfig:
    overrides = {
        "from_year": args.year_from,
        "to_year": args.year_to,
        "cast_cap": args.cap,
        "min_sitelinks": args.min_sitelinks,
        "min_cast": args.min_cast,
    }
    overrides = {k: v for k, v in overrides.items() if v is not None}
    return replace(BuildConfig(), **overrides)


def main() -> None:
    parser = argparse.ArgumentParser(prog="etl")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="extract → transform → emit")
    build.add_argument("--year-from", dest="year_from", type=int)
    build.add_argument("--year-to", dest="year_to", type=int)
    build.add_argument("--cap", type=int, help="cast_cap: top-N actors per film")
    build.add_argument("--min-sitelinks", dest="min_sitelinks", type=int)
    build.add_argument("--min-cast", dest="min_cast", type=int)
    build.add_argument("--version", default="v1", help="output dir under graph/")

    args = parser.parse_args()
    config = _config_from_args(args)

    extract.extract(config)              # Stage 1 — network, cached
    edges = transform.transform(config)  # Stage 2 — pure, writes edges.jsonl
    emit.emit(edges, config, args.version)  # Stage 3 — pure, writes graph/<version>/
    print(f"done: graph/{args.version}/")


if __name__ == "__main__":
    main()
```

---

## Tests — where the value is

Concentrate on the **pure** stages (transform, emit). Keep extract thin and mostly out of the fast
suite.

### `tests/conftest.py` — a tiny row/edge factory

```python
from etl.models import Actor, Edge, Film


def film(qid: str, *cast: tuple[str, int], sitelinks: int = 100) -> Film:
    """film('Q1', ('Q10', 50), ('Q11', 90)) → Film with two cast at those sitelink counts."""
    f = Film(qid, f"label-{qid}", sitelinks)
    for actor_qid, links in cast:
        f.cast[actor_qid] = Actor(actor_qid, f"label-{actor_qid}", links)
    return f


def edge(movie: str, actor: str) -> Edge:
    return Edge(movie, f"label-{movie}", actor, f"label-{actor}")
```

### `tests/test_transform.py` — the important ones

```python
from etl.config import BuildConfig
from etl.transform import cap_cast, films_to_edges, load_films
from tests.conftest import film


def _actors(edges, movie):
    return sorted(e.actor for e in edges if e.movie == movie)


def test_cap_keeps_top_n_by_actor_sitelinks():
    f = film("Q1", ("Q10", 10), ("Q11", 90), ("Q12", 50))
    edges = films_to_edges({"Q1": f}, BuildConfig(min_cast=1, cast_cap=2))
    assert _actors(edges, "Q1") == ["Q11", "Q12"]        # 90 and 50, not 10


def test_cap_ties_break_by_qid_deterministically():
    f = film("Q1", ("Q11", 50), ("Q10", 50), ("Q12", 50))  # all tied
    kept = [a.qid for a in cap_cast(f.cast, 2)]
    assert kept == ["Q10", "Q11"]                        # lowest QIDs win, stable across runs


def test_min_cast_floor_is_a_strict_boundary():
    below = film("Q1", ("Q10", 9), ("Q11", 9))           # 2 cast
    at = film("Q2", ("Q20", 9), ("Q21", 9), ("Q22", 9))  # 3 cast
    edges = films_to_edges({"Q1": below, "Q2": at}, BuildConfig(min_cast=3, cast_cap=15))
    assert _actors(edges, "Q1") == []                    # dropped
    assert len(_actors(edges, "Q2")) == 3                # kept


def test_duplicate_rows_across_partitions_collapse(tmp_path):
    import json
    # same (film, actor) in two year files → one distinct cast member, one edge
    for year in (1994, 1995):
        (tmp_path / f"films-{year}.json").write_text(json.dumps({
            "rows": [{"film": "Q1", "film_label": "F", "film_sitelinks": 100,
                      "actor": "Q10", "actor_label": "A", "actor_sitelinks": 50}]}))
    films = load_films(sorted(tmp_path.glob("films-*.json")))
    assert list(films["Q1"].cast) == ["Q10"]
```

### `tests/test_emit.py` — the invariants

```python
from etl.emit import build_adjacency, build_entities
from tests.conftest import edge


def test_symmetry_property():
    edges = [edge("Q1", "Q10"), edge("Q1", "Q11"), edge("Q2", "Q10")]
    m2a, a2m = build_adjacency(edges)
    for movie, actors in m2a.items():
        for actor in actors:
            assert movie in a2m[actor]
    for actor, movies in a2m.items():
        for movie in movies:
            assert actor in m2a[movie]


def test_entities_typed_and_deduped():
    ents = build_entities([edge("Q1", "Q10"), edge("Q1", "Q10")])
    assert ents["Q1"]["type"] == "movie"
    assert ents["Q10"]["type"] == "actor"


def test_emit_is_byte_deterministic(tmp_path, monkeypatch):
    import json
    from etl import emit as emit_mod, paths
    from etl.config import BuildConfig
    monkeypatch.setattr(paths, "GRAPH_DIR", tmp_path)         # redirect output
    monkeypatch.setattr(paths, "RAW_DIR", tmp_path / "raw")   # no raw files → query_date {from:None,to:None}
    edges = [edge("Q1", "Q11"), edge("Q1", "Q10"), edge("Q2", "Q10")]
    emit_mod.emit(edges, BuildConfig(), "v1")
    first = (tmp_path / "v1" / "graph.json").read_bytes()
    emit_mod.emit(edges, BuildConfig(), "v1")                 # overwrite
    assert (tmp_path / "v1" / "graph.json").read_bytes() == first
```

### `tests/test_extract.py` — thin, no network in the fast suite

```python
import pytest

from etl.config import BuildConfig
from etl.extract import render_query


def test_query_is_templated_from_config():
    q = render_query(1994, BuildConfig(min_sitelinks=7))
    assert "YEAR(?date) = 1994" in q
    assert "?filmSitelinks >= 7" in q
    assert "en.wikipedia.org" in q
    assert "en.wikipedia.org" not in render_query(1994, BuildConfig(require_enwiki=False))


@pytest.mark.live
def test_live_smoke_one_year():
    from etl import sparql
    rows = sparql.query(render_query(1994, BuildConfig()), BuildConfig())
    assert rows and rows[0]["film"].startswith("Q")
    assert isinstance(rows[0]["actor_sitelinks"], int)
```

Run the fast suite with `uv run pytest` (the `live` test is deselected because it's marked and you don't
pass `-m live`). Run the smoke test deliberately with `uv run pytest -m live`.

> If pytest *runs* the live test by default, you're missing the `markers`/deselect setup. Simplest fix:
> add `addopts = "-m 'not live'"` under `[tool.pytest.ini_options]`, or `@pytest.mark.skip`-guard it
> behind an env var. The registered marker in 00-scaffolding keeps pytest from warning either way.

---

## Verification — Phase 1 "done when"

ROADMAP: *"a documented offline run produces a loadable, versioned artifact from scratch."* Concretely,
with the **default config (years 1900–2026)**:

1. **Clean build runs end-to-end.** From a fresh `etl/`: `uv sync`, then `uv run python -m etl build`
   completes: `data/raw/*.json` → `data/interim/edges.jsonl` → `graph/v1/`.
2. **Counts are in the right ballpark.** `graph/v1/manifest.json` shows `n_movies` ~50k and `n_edges` in
   the hundreds of thousands (EXPLORATION: ~51k usable films, ~593k raw edges pre-cap; post-cap edges
   are fewer).
3. **Symmetry + real-chain load check** (the throwaway script from 03-emit's verify section): load
   `graph.json`, assert every `movie→actor` has its inverse, and spot-check *Inception* (`Q25188`) →
   DiCaprio (`Q38111`) and DiCaprio → *Titanic* (`Q44578`). This proves the O(1) lookup the server will
   do is correct against real data.
4. **Reproducibility.** Re-run `uv run python -m etl build`:
   - extract prints `skip <year> (cached)` for every year — **no new network calls**;
   - `graph/v1/graph.json` is **byte-identical** to the previous run
     (`shasum graph/v1/graph.json` before and after match).
5. **Green gates.** `uv run pytest` passes; `uv run ruff check` clean; `uv run basedpyright` clean.

Quick one-liner for step 4's reproducibility hash:

```bash
shasum graph/v1/graph.json && uv run python -m etl build >/dev/null && shasum graph/v1/graph.json
# the two hashes must match
```

---

## Deliberately out of scope (from the guide — don't build these now)

- **Wikidata dumps path** — SPARQL partitioning is enough at this scale.
- **MediaWiki Action API entity-detail fetch** — only for per-entity fields the SPARQL rows don't carry.
- **`P1545` billing order as a real signal** — ~8% coverage; we already tiebreak on QID.
- **Kotlin loader / QID→Int mapping** — Phase 2, server-side, not this artifact's concern.
