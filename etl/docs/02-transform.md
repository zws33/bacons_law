# Stage 2 — Transform (answer key)

**Goal:** fold the denormalized raw rows into a **capped, deterministic** edge list.

**Consumes:** `data/raw/films-*.json` (the wrappers from Stage 1).
**Produces:** `data/interim/edges.jsonl` — one `{"movie","movie_label","actor","actor_label"}` per line.

**This stage is pure** (no I/O except reading its inputs and the one final write), so it's where the
unit tests concentrate. Guide reference: [../IMPLEMENTATION_GUIDE.md](../IMPLEMENTATION_GUIDE.md)
§"Stage 2".

---

## The pipeline, in order

1. **Load + group by film** → `dict[str, Film]`. Keyed by film QID so duplicate rows across year
   partitions collapse for free (a film with two publication years appears in two raw files; same QID →
   one `Film`).
2. **Min-cast floor** — drop films with `< config.min_cast` *distinct* cast. Required, not optional:
   EXPLORATION shows ~25% of notable films have <3 cast, so the notability filter alone is insufficient.
3. **Cast-depth cap** — for each surviving film, sort its cast by **actor sitelink count descending**,
   take the top `config.cast_cap`. This is the EXPLORATION pivot (billing order `P1545` is unusable, so
   actor notability *is* the ranking).
4. **Emit edges**, deterministically ordered, to `edges.jsonl`.

## `src/etl/transform.py`

```python
import json

from etl import paths
from etl.config import BuildConfig
from etl.models import Actor, Edge, Film


def load_films(raw_paths: list) -> dict[str, Film]:
    """Read every raw wrapper, accumulate per-film distinct cast. QID keys dedup across partitions."""
    films: dict[str, Film] = {}
    for path in raw_paths:
        payload = json.loads(path.read_text())
        for row in payload["rows"]:
            film = films.get(row["film"])
            if film is None:
                film = Film(row["film"], row["film_label"], row["film_sitelinks"])
                films[film.qid] = film
            # setdefault: first sighting of an actor wins; later duplicate rows are ignored.
            film.cast.setdefault(
                row["actor"],
                Actor(row["actor"], row["actor_label"], row["actor_sitelinks"]),
            )
    return films


def cap_cast(cast: dict[str, Actor], n: int) -> list[Actor]:
    """Top-n actors by sitelink count. Tie-break on QID so the result is deterministic (see below)."""
    return sorted(cast.values(), key=lambda a: (-a.sitelinks, a.qid))[:n]


def films_to_edges(films: dict[str, Film], config: BuildConfig) -> list[Edge]:
    """Pure core: (films, config) -> deterministic edge list. This is the heavily-tested function."""
    edges: list[Edge] = []
    for film in films.values():
        if len(film.cast) < config.min_cast:          # step 2: floor on DISTINCT cast
            continue
        for actor in cap_cast(film.cast, config.cast_cap):  # step 3: cap
            edges.append(Edge(film.qid, film.label, actor.qid, actor.label))
    edges.sort(key=lambda e: (e.movie, e.actor))       # step 4: total order → byte-reproducible output
    return edges


def transform(config: BuildConfig) -> list[Edge]:
    """Stage entry: read raw cache, fold to edges, write edges.jsonl, return edges for the emit stage."""
    raw_paths = sorted(paths.RAW_DIR.glob("films-*.json"))
    films = load_films(raw_paths)
    edges = films_to_edges(films, config)
    write_edges(edges, paths.edges_path())
    return edges


def write_edges(edges: list[Edge], path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for e in edges:
            line = {
                "movie": e.movie,
                "movie_label": e.movie_label,
                "actor": e.actor,
                "actor_label": e.actor_label,
            }
            f.write(json.dumps(line) + "\n")
```

## The three things that are easy to get subtly wrong

### Determinism (the load-bearing detail)
Two builds of the same raw cache must produce a **byte-identical** `edges.jsonl`, so you can `diff` two
builds and see only real catalog changes. Two places enforce it:
- **`cap_cast` tie-break:** `key=(-a.sitelinks, a.qid)`. Without the `a.qid` secondary key, actors tied
  on sitelink count sort in arbitrary (hash/insertion) order, and the *boundary* of the top-N cut flips
  between runs. This is the single most important line in the stage.
- **`films_to_edges` final sort:** `dict` iteration order follows insertion, which follows raw-file read
  order — stable today, but sorting by `(movie, actor)` makes the output independent of it. Belt and
  suspenders, but cheap.

### Floor vs. cap ordering
Apply the **floor to the full distinct cast** (`len(film.cast)`), *then* cap. A film with 2 cast is
dropped entirely; a film with 50 is kept and capped to 15. Don't cap first — you'd never drop the
sparse films the floor exists to remove.

### Distinct means distinct
The floor counts *distinct* cast members (`dict` size), and `setdefault` guarantees an actor appearing
in duplicate rows across partitions is counted once. If you accumulated a `list` instead of a `dict`,
duplicates would inflate the count and defeat the floor.

## Why keep it pure
`(films, config) → edges` with no network, no clock, no globals is trivially unit-testable and mirrors
the `:core` purity discipline on the Kotlin side. `load_films`/`write_edges` are the thin I/O rind;
`films_to_edges` + `cap_cast` are the pure center where every test lives (see 04-testing).

---

## Verify Stage 2 in isolation

**Against the pure function, no files:**

```bash
uv run python -c "
from etl.config import BuildConfig
from etl.models import Actor, Film
from etl.transform import films_to_edges

# one film, 4 cast, cap 2 → keep the two highest-sitelink actors
f = Film('Q1', 'F', 100, cast={
    'Q10': Actor('Q10','A',50), 'Q11': Actor('Q11','B',50),   # tie at 50 → QID breaks it (Q10 < Q11)
    'Q12': Actor('Q12','C',90), 'Q13': Actor('Q13','D',10),
})
edges = films_to_edges({'Q1': f}, BuildConfig(min_cast=3, cast_cap=2))
kept = sorted(e.actor for e in edges)
assert kept == ['Q10','Q12'], kept       # C(90) then the tie winner Q10 over Q11
print('cap + tiebreak OK')

# a 2-cast film is dropped by the floor
g = Film('Q2','G',100, cast={'Q20':Actor('Q20','X',9),'Q21':Actor('Q21','Y',9)})
assert films_to_edges({'Q2': g}, BuildConfig(min_cast=3)) == []
print('min_cast floor OK')
"
```

**Against the real raw cache** (after a Stage 1 run): `uv run python -m etl build` writes
`data/interim/edges.jsonl`; sanity-check it:

```bash
wc -l data/interim/edges.jsonl                    # hundreds of thousands post-cap
head -1 data/interim/edges.jsonl                  # {"movie":"Q…","movie_label":…,"actor":"Q…",…}
```
