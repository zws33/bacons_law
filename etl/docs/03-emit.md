# Stage 3 — Emit (answer key)

**Goal:** build both adjacency directions + the typeahead entity index, and write a **versioned,
self-describing** artifact.

**Consumes:** the `list[Edge]` from Stage 2 (and the raw wrappers, for provenance dates).
**Produces:** `graph/<version>/manifest.json` + `graph/<version>/graph.json`.

Also pure. Guide reference: [../IMPLEMENTATION_GUIDE.md](../IMPLEMENTATION_GUIDE.md) §"Stage 3".

---

## The artifact shape (the contract the Kotlin loader will read)

```
graph/v1/
  manifest.json   # schema_version, source, query_date range, config params, counts, generated_at
  graph.json      # { "movies": {qid:[actorQid,…]}, "actors": {qid:[movieQid,…]},
                  #   "entities": {qid:{"label","type"}} }
```

Keys are **Wikidata QIDs (strings)** — provenance-inline and stable (ADR 010). The engine's
`castIds: Set<Int>` contract is a **loader-side** concern; the Kotlin loader assigns its own int IDs.
**Do not pre-map to ints here** — the artifact stays QID-keyed.

## `src/etl/emit.py`

```python
import json
from collections import defaultdict
from datetime import datetime, timezone

from etl import paths
from etl.config import BuildConfig
from etl.models import Edge

SCHEMA_VERSION = 1


def build_adjacency(edges: list[Edge]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """Build movie→actors, then DERIVE actor→movies by inverting it (symmetry is structural, D-guide §4)."""
    movie_to_actors: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        movie_to_actors[e.movie].add(e.actor)

    actor_to_movies: dict[str, set[str]] = defaultdict(set)
    for movie, actors in movie_to_actors.items():
        for actor in actors:
            actor_to_movies[actor].add(movie)

    return movie_to_actors, actor_to_movies


def build_entities(edges: list[Edge]) -> dict[str, dict]:
    """qid -> {'label', 'type'} for typeahead. Only entities that survived the cap appear."""
    entities: dict[str, dict] = {}
    for e in edges:
        entities.setdefault(e.movie, {"label": e.movie_label, "type": "movie"})
        entities.setdefault(e.actor, {"label": e.actor_label, "type": "actor"})
    return entities


def _sorted_lists(m: dict[str, set[str]]) -> dict[str, list[str]]:
    """JSON has no set type: sort each adjacency set to a list so output is deterministic + diffable."""
    return {qid: sorted(neighbors) for qid, neighbors in m.items()}


def _query_date_range() -> dict[str, str]:
    """Min/max fetched_at across the raw cache (D6). A pull can span days; record the span."""
    stamps = []
    for path in sorted(paths.RAW_DIR.glob("films-*.json")):
        header = json.loads(path.read_text())
        if "fetched_at" in header:
            stamps.append(header["fetched_at"])
    if not stamps:
        return {"from": None, "to": None}
    return {"from": min(stamps), "to": max(stamps)}


def emit(edges: list[Edge], config: BuildConfig, version: str) -> None:
    movie_to_actors, actor_to_movies = build_adjacency(edges)
    entities = build_entities(edges)

    graph = {
        "movies": _sorted_lists(movie_to_actors),
        "actors": _sorted_lists(actor_to_movies),
        "entities": entities,
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "version": version,
        "source": "wikidata",
        "query_date": _query_date_range(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "min_sitelinks": config.min_sitelinks,
            "min_cast": config.min_cast,
            "cast_cap": config.cast_cap,
            "require_enwiki": config.require_enwiki,
            "from_year": config.from_year,
            "to_year": config.to_year,
        },
        "counts": {
            "n_movies": len(movie_to_actors),
            "n_actors": len(actor_to_movies),
            "n_edges": len(edges),
        },
    }

    out = paths.graph_version_dir(version)
    out.mkdir(parents=True, exist_ok=True)
    # sort_keys=True → every object key ordered; combined with pre-sorted lists this is byte-reproducible.
    (out / "graph.json").write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n")
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
```

## The four things worth understanding

### 1. Derive the inverse — don't build it twice
`actor_to_movies` is built by inverting `movie_to_actors`, **not** by a second independent pass over
edges. This makes asymmetry *structurally impossible*: every `actor ∈ movie_to_actors[m]` is guaranteed
to have `m ∈ actor_to_movies[actor]`, because that's literally the loop that created it. (The emit
invariant test in 04-testing checks this property, but the construction is what makes it hold.)

### 2. Determinism = pre-sorted lists **and** `sort_keys=True`
- Sets → **sorted** lists (`_sorted_lists`): JSON has no set, and unsorted lists would reorder run to
  run.
- `json.dumps(..., sort_keys=True)`: orders every *object* key (the QID keys of the maps, and
  `label`/`type` within each entity) regardless of insertion order.

Together these make `graph.json` byte-identical across runs on the same edges — the reproducibility
check (04-testing / Verification step 4) depends on it. The trailing `+ "\n"` is just so the file ends
in a newline (POSIX-friendly, cleaner diffs).

### 3. The manifest is what makes it an *artifact*, not a dump
It records the **exact config** (the gameplay dials must travel *with* the data), the **counts** (quick
sanity/regression signal), the **query_date range** (provenance — when the underlying Wikidata was
observed), and a separate **generated_at** (when this emit ran). The server loads *a specific version*;
a build is only reproducible if it says what went into it.

### 4. Versioning (D5)
`version` names the directory (`graph/v1/`). Re-running the same version **overwrites** it — safe
precisely because emit is deterministic, so an overwrite with the same inputs is a no-op at the byte
level. A re-tuned build is a *new* `--version v2`, sitting beside `v1`, never an in-place mutation of a
shipped version. No auto-increment: it would make "run it again" produce a different path each time and
break the reproducibility check.

### On deferring search
If you chose to skip typeahead: drop `build_entities` and the `"entities"` key. Nothing else changes —
`movies`/`actors` are independent of it. The label columns on `Edge` simply go unused (harmless).

---

## Verify Stage 3 in isolation

**Pure, from hand-built edges:**

```bash
uv run python -c "
from etl.config import BuildConfig
from etl.models import Edge
from etl.emit import build_adjacency, build_entities

edges = [Edge('Q1','F1','Q10','A'), Edge('Q1','F1','Q11','B'), Edge('Q2','F2','Q10','A')]
m2a, a2m = build_adjacency(edges)
# symmetry: every forward edge has its inverse
for m, actors in m2a.items():
    for a in actors:
        assert m in a2m[a], (m, a)
assert a2m['Q10'] == {'Q1','Q2'}          # A is in both films
ents = build_entities(edges)
assert ents['Q1']['type'] == 'movie' and ents['Q10']['type'] == 'actor'
print('adjacency + symmetry + entities OK')
"
```

**Full artifact + real-data spot check** (after `uv run python -m etl build`):

```bash
uv run python -c "
import json
g = json.load(open('graph/v1/graph.json'))
m = json.load(open('graph/v1/manifest.json'))
print('counts:', m['counts'])
# real chain: Inception contains DiCaprio; DiCaprio's films contain Titanic
assert 'Q38111' in g['movies']['Q25188']          # Inception -> DiCaprio
assert 'Q44578' in g['actors']['Q38111']          # DiCaprio -> Titanic
print('real-data chain OK')
"
```

If a QID is missing from that last check, it usually means the film fell below `min_sitelinks`, the
actor was cut by `cast_cap`, or the year is outside `from_year..to_year` — check the manifest config,
not the emit code.
