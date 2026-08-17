# etl — the offline graph build

Builds the versioned actor↔movie graph artifact that the Bacon's Law server loads into Postgres.
Source is CC0 Wikidata over SPARQL (QLever). Runs **offline** — it is never in the request path, and
there is no API key.

```sh
uv sync
uv run python -m etl build --year-from 1925 --year-to 2026 --out-version v2
```

Three stages with a disk cache between each, individually invokable — `extract` is slow and
network-bound, `transform` and `emit` are pure and fast, so retuning a gameplay dial costs a
`transform && emit` rather than a re-pull:

| Stage | Reads | Writes |
|---|---|---|
| `extract` | QLever | `data/raw/films-YYYY.json` |
| `transform` | `data/raw/` | `data/interim/edges.jsonl` |
| `emit` | `data/interim/edges.jsonl` | `data/graph/<version>/{graph,manifest}.json` |

`graph.json` holds `movies_to_actors` and `actors_to_movies` (QID → sorted QIDs, the O(1)
set-membership check the server validates moves against) plus `entities` (QID → `{label, type,
sitelinks}`, with `year` on movies). Labels and years are what a typeahead renders; `sitelinks` is
what it ranks on ([ADR 020](../docs/DECISIONS.md)).

`data/` is gitignored and a full pull is ~100 sequential queries against a best-effort third-party
endpoint — **back up `data/raw/` once you have it.**

Development commands and the decisions behind the pipeline are in [AGENTS.md](AGENTS.md).

## The current artifact

`v2` (schema 3; 1925–2026, `cast_cap` 15, `min_cast` 3, `min_sitelinks` 5) was emitted 2026-08-17
from the 2026-08-04/05 raw pull: **47,624 movies · 89,074 actors · 456,129 edges · 23MB.** Symmetric,
`entities` exactly equal to the node set, 100% of movies labelled, 1.31% of actors unlabelled. Cast
per movie 3–15, 25.6% at the cap. Movie sitelinks 5–138, actor sitelinks 0–339 — the movie floor is
`min_sitelinks`, which gates films only.

Schema 3 put `sitelinks` on every entity for typeahead ranking; schema 2 put `year` on movies. `v1`
(schema 2, same node set) sits unchanged beside it.

Two known fidelity gaps, both deliberately deferred — see
[issue #19](https://github.com/zws33/bacons_law/issues/19): nine QIDs are both a movie and an actor
node (the query puts no type constraint on the object of `P161`), and the documentary/TV-film
exclusions miss items Wikidata tags only as `film`. Neither affects move validation, but the second
is plainly visible in ranking: the top-sitelink "actors" are Barack Obama, Adolf Hitler, Albert
Einstein, and Fiji — documentary subjects ranked on global notability. Film count does not separate
them (Reagan 65 films, Hitler 36), so the fix is a `P106` occupation constraint in the re-extract,
not a ranking tweak.

## Verifying an artifact

Spot-check that a graph is *correct*, not merely *produced*. Run from `etl/`, substituting the version:

```sh
uv run python - <<'EOF'
import collections, json
V = 'v2'
g = json.load(open(f'data/graph/{V}/graph.json'))
m2a, a2m, ent = g['movies_to_actors'], g['actors_to_movies'], g['entities']
print('movies', len(m2a), 'actors', len(a2m), 'entities', len(ent))

bad  = sum(1 for mv, c in m2a.items() for a in c if mv not in a2m.get(a, ()))
bad += sum(1 for a, fs in a2m.items() for mv in fs if a not in m2a.get(mv, ()))
print('symmetry violations:', bad)                       # must be 0
print('entities == nodes:', set(ent) == set(m2a) | set(a2m))
print('type overlap:', len(set(m2a) & set(a2m)))         # QIDs that are both — see issue #19

unl = [q for q, e in ent.items() if e['label'] == q]
print('unlabeled:', collections.Counter(ent[q]['type'] for q in unl))

pairs = {(mv, a) for mv, c in m2a.items() for a in c}
print('n_edges matches graph:',
      json.load(open(f'data/graph/{V}/manifest.json'))['counts']['n_edges'] == len(pairs))

sizes = [len(c) for c in m2a.values()]
print('cast/movie: min', min(sizes), 'max', max(sizes))  # must be within [min_cast, cast_cap]

print('missing sitelinks:', sum(1 for e in ent.values() if not isinstance(e.get('sitelinks'), int)))
for t in ('movie', 'actor'):                             # movie floor == min_sitelinks; actors 0
    s = [(e['sitelinks'], e['label']) for e in ent.values() if e['type'] == t]
    print(f'{t} sitelinks: min', min(s)[0], 'max', max(s)[0], '| top:',
          ', '.join(l for _, l in sorted(s, reverse=True)[:8]))
EOF
```

**Expected:** 0 symmetry violations, `entities` exactly equal to the node set, `n_edges` matching, and
cast sizes inside `[min_cast, cast_cap]`. Any unlabeled **movies** is the signal to investigate —
films are anchored to an English Wikipedia article, so the article-title fallback should cover every
one of them. Unlabeled **actors** are expected and fine (no anchor applies); ~1.5% is normal and a
much larger figure is not.

Every entity carries an int `sitelinks`, and the **movie** minimum must equal `min_sitelinks` — that
is what catches the film and actor counts being wired to the wrong entity type, since the actor floor
is 0 and would swallow a swap silently. The top-label lists are the same check by eye: recognisable
films means the field landed where it belongs. The top *actors* are heads of state, not actors —
expected, and explained above.

Note that `entities == nodes` compares *sets*, so it passes even when a QID is keyed as both a movie
and an actor. The separate `type overlap` line is what catches that.

## Known follow-ons

Deferred deliberately — none is a bug, and none blocks a build.

- **Collapse year partitioning into a single query.** `data/spike/films-all.rq` shows QLever returns
  the full range in one pull, with no 60s wall to hide under. Doing it would delete the per-year
  cache, the failed-year accounting, and the resume logic — rewriting `_cache_is_valid`, `_load_rows`,
  and much of `test_pipeline` to save one-time runtime on a pipeline that runs rarely, while losing
  resumability on a ~100-query pull. Not worth it as things stand.
- **Incremental update path.** There is no "fetch year N+1 and merge into an existing artifact"
  command; `build` always re-emits from the full raw cache. That is cheap today (transform and emit
  are pure and fast over cached files), so the update cadence is: re-run `extract` for the new year,
  then `build`. Worth designing properly before the first real refresh.

**Batch every query change into one rebuild.** Issue #19's fixes require a full re-extract, the one
expensive step in the pipeline. Anything that touches the SPARQL query waits for that rebuild and goes
in with it, bumping `QUERY_VERSION` once. Not urgent —
[ADR 019](../docs/DECISIONS.md) measured the confound at 0.02% of degree-1 actors.
