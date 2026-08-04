# Repair Plan — get the pipeline to a working state

**Status:** Phases 0–2 are **done** (branch `fix/etl-pipeline-repair`, PR #14). Only **Phase 3**, the
full build, is outstanding. Delete this file once the graph exists and the project moves to its own
Phase 2 (the Kotlin loader) — not to be confused with this document's Phase 2 below.

The completed phases are kept for the reasoning, not as instructions; the code has moved past them.

## Diagnosis

The working tree is a half-finished migration. Committed `HEAD` resolved labels in a **separate
post-transform stage** (`resolve_labels.py` → `labels.json`) because `SERVICE wikibase:label` blew the
WDQS 60s wall. The QLever migration made that unnecessary — `OPTIONAL { ?film rdfs:label ?filmLabel }`
comes back inline, so emit builds `entities` from the labels carried on the edges.

The source already moved: `WikidataRow` and `Edge` carry labels, the query selects them, and
`paths.labels_path()` was **deleted**. Three things never followed:

| Broken | Why |
| --- | --- |
| `emit.py:98` calls `paths.labels_path()` | function no longer exists → `AttributeError` |
| `resolve_labels.py` + its `resolve` subcommand | dead stage, also calls `labels_path()`, still in the `build` chain (`__main__.py:141`) |
| `test_transform` / `test_sparql` / `test_emit` / `test_pipeline` | still assert the label-less `HEAD` shape |

62 failing tests looks alarming, but they collapse out of ~4 helper functions.

**Ordering rationale:** Phase 0 before anything because a dead endpoint invalidates the rest. Phase 1
before Phase 2 because fixing tests against a broken source means fixing them twice. Phase 2 before
Phase 3 because `test_transform` and `test_emit` are the only things that distinguish a correct graph
from a produced one, and Phase 3 costs an hour of wall-clock you don't want to spend twice.

---

## Phase 0 — Prove QLever works (do this first) ✅ done

Everything downstream assumes `qlever.dev` answers the labeled query. If it doesn't, the plan changes.

### 0.1 Fix `smoke.py` so it can't poison the cache

`src/etl/smoke.py:37` writes a **bare list** to `raw_path(year)` — the real cache path.
`transform._load_rows()` validates every `films-*.json` with `CachePayload`, so that file will hard-fail
the transform stage.

Change the write target so it falls outside the `films-*.json` glob:

```python
path = RAW_DIR / f"smoke-{year}.json"
```

Leave the rest alone. (`raw_path` becomes an unused import — drop it from line 15.)

### 0.2 Clear stale WDQS-era state

`data/raw/films-2015.json` was pulled from `query.wikidata.org` and has no label columns.
`_cache_is_valid` will refetch it (endpoint mismatch), but a bare `transform` run before that would
crash.

```sh
rm data/raw/films-2015.json data/labels.json data/interim/edges.jsonl
rm -rf data/graph/v1
```

`data/graph/v1` has to go regardless: its manifest config still carries `require_enwiki`, so
`_check_version_is_free` will refuse to overwrite it.

### 0.3 Run the smoke

```sh
uv run python -m etl.smoke 2015
```

**What you're checking:** it returns rows at all (endpoint reachable, `PREFIX` block accepted — QLever
has no default prefixes), and the sampled rows show real `film_label` / `actor_label` values rather than
QIDs echoed back. A QID in the label field means the `OPTIONAL` didn't bind; a few of those on actors is
expected and correct, but if *every* row shows QIDs, `rdfs:label` isn't resolving and you should stop
here.

Sanity number: 2015 gave 23,283 rows on WDQS at `min_sitelinks=5`. QLever should be in the same
ballpark.

---

## Phase 1 — Finish the label removal (the actual blocker) ✅ done

### 1.1 `src/etl/emit.py`

Three edits:

- **Delete `_load_labels()` entirely** (lines 97–102). It calls `paths.labels_path()`, which no longer
  exists — this is the `AttributeError` behind most of the emit failures.
- **Delete `labels = _load_labels()`** (line 31).
- **Rewrite `_build_entities`** to take labels off the edges:

```python
def _build_entities(edges: list[Edge]) -> dict[str, dict[str, str]]:
    """qid → {label, type}: the typeahead index Phase 4 search resolves names against."""
    entities: dict[str, dict[str, str]] = {}
    for e in edges:
        entities[e.movie] = {"label": e.movie_label, "type": "movie"}
        entities[e.actor] = {"label": e.actor_label, "type": "actor"}
    return entities
```

Then update the call site (line 35) to `_build_entities(edges)`.

This also removes a latent `KeyError`: the old version did `labels[e.movie]`, which would blow up on any
QID missing from `labels.json`. `sparql._flatten` already falls back to the QID string, so
`e.movie_label` is never absent.

### 1.2 Delete the dead stage

```sh
rm src/etl/resolve_labels.py tests/test_resolve_labels.py
```

### 1.3 `src/etl/__main__.py` — unwire it

Removals:

- line 16: `from etl.resolve_labels import resolve_labels`
- lines 73–75: the `_run_resolve_labels` function
- lines 105–108: the `resolve_cmd` subparser block
- lines 135–136: the `elif args.command == "resolve":` branch
- line 141: `_run_resolve_labels(config)` in the `build` chain

Also fix the module docstring (lines 1–6): it says "four-stage" and "runs all four" — it's three stages
now, and `resolve` is no longer "slow and network-bound."

### Checkpoint

```sh
uv run ruff check . && uv run basedpyright
```

Pyright is the one that matters here — it catches any remaining reference to `labels_path` or
`resolve_labels`. Ruff won't, because `paths.labels_path()` is an attribute access, not a bare name
(this is exactly why ruff reported "All checks passed" on a broken tree).

---

## Phase 2 — Repair the tests ✅ done

62 failures, but they collapse out of four helper functions. Work in this order — `test_sparql` first,
since it's the narrowest.

### 2.1 `tests/test_sparql.py` (2 failures)

**`_binding()`** — add the two label bindings. Keep them optional so you can still exercise the unbound
path:

```python
def _binding(
    film: str, actor: str, film_links: int, actor_links: int,
    film_label: str | None = None, actor_label: str | None = None,
) -> _Row:
    b = {
        "film": {"type": "uri", "value": f"http://www.wikidata.org/entity/{film}"},
        "filmSitelinks": {"type": "literal", "value": str(film_links)},
        "actor": {"type": "uri", "value": f"http://www.wikidata.org/entity/{actor}"},
        "actorSitelinks": {"type": "literal", "value": str(actor_links)},
    }
    if film_label is not None:
        b["filmLabel"] = {"type": "literal", "value": film_label}
    if actor_label is not None:
        b["actorLabel"] = {"type": "literal", "value": actor_label}
    return b
```

**`test_flatten_maps_all_four_fields`** — pass labels in and add `film_label` / `actor_label` to the
expected dict. Rename it while you're there; it's six fields now.

**`test_query_wraps_http_error`** — asserts `match="WDQS request failed"`, but `sparql.py:51` now raises
`"Request failed: …"`. Change the match to `"Request failed"`. Fix the test, not the source — the
message was deliberately de-WDQS'd for QLever.

**Add one test** for the unbound-label fallback. An unbound `OPTIONAL` is *omitted from the binding
object*, not present-as-null, and the QID fallback is what restores the guarantee
`SERVICE wikibase:label` used to give you:

```python
def test_flatten_falls_back_to_qid_when_label_is_unbound():
    rows = _flatten(_payload(_binding("Q1", "Q10", 100, 50)))  # no labels
    assert rows[0]["film_label"] == "Q1"
    assert rows[0]["actor_label"] == "Q10"
```

This is the single highest-value test in the repair — it's the one failure mode that will actually bite
on the real 102-year run.

### 2.2 `tests/test_transform.py` (17 failures)

**`_row()`** — add the two label params:

```python
def _row(
    film: str = "Q1", film_sitelinks: int = 100,
    actor: str = "Q10", actor_sitelinks: int = 50,
    film_label: str = "", actor_label: str = "",
) -> WikidataRow:
    return WikidataRow(
        film=film, film_label=film_label or film, film_sitelinks=film_sitelinks,
        actor=actor, actor_label=actor_label or actor, actor_sitelinks=actor_sitelinks,
    )
```

Defaulting the label to the QID keeps every existing `_build_edge_list` assertion valid unchanged —
those all assert on `.movie` / `.actor`, never labels.

**The `_cap_cast` tests are the one genuine reshape.** The signature changed from
`dict[str, int] -> list[tuple[str, int]]` to `dict[str, Actor] -> list[Actor]`. Add a helper:

```python
def _cast(*pairs: tuple[str, int]) -> dict[str, Actor]:
    return {qid: Actor(qid=qid, label=qid, sitelinks=n) for qid, n in pairs}
```

Then each test becomes `_cap_cast(_cast(("Q10", 50)), cap=5)` with assertions on
`[a.qid for a in result]`. Seven tests, mechanical. `test_cap_cast_single_actor` asserts
`== [("Q10", 50)]` — that becomes `[a.qid for a in result] == ["Q10"]`.

Import `Actor` from `etl.models`.

### 2.3 `tests/test_emit.py` (22 failures)

**`_edge()`** — one edit fixes nearly all 22:

```python
def _edge(movie: str = "Q1", actor: str = "Q10") -> Edge:
    return Edge(movie=movie, movie_label=f"Film {movie}",
                actor=actor, actor_label=f"Actor {actor}")
```

**Delete `_write_labels()`** (line ~55) and every call to it.

**`test_build_entities_labels_and_types_both_sides`** — drop the `labels` argument from the
`_build_entities` call; expectations stay `{"label": "Film Q1", "type": "movie"}` with the naming above.

### 2.4 `tests/test_pipeline.py` (12 failures)

The largest file but the edits are subtractive:

- **Remove** `resolve_labels` from the import on line 24.
- **Delete** `_FakeWBResponse`, `FakeWBEntities`, and the `wbapi` autouse fixture. There's no second
  network surface anymore.
- **`_binding()`** — stop discarding the labels. `CATALOG` already carries them; the current version
  unpacks them into `_film_label` / `_actor_label` and throws them away. Add
  `"filmLabel": {"value": film_label}` and `"actorLabel": {"value": actor_label}`.
- **Fix the `_binding` docstring** — it currently says "Labels are NOT included: the SPARQL query no
  longer fetches them (doing so caused timeouts)." That's the WDQS-era rationale and it's now inverted.
- **`_build()`** — delete the `resolve_labels.resolve_labels(cfg)` line.

`test_pipeline_entities_carry_labels_from_wikidata` should then pass unchanged, and its docstring gets
*more* accurate — labels now genuinely travel query → raw cache → edges → index in one path.

### Checkpoint

```sh
uv run pytest -q
```

Target: 0 failed. (Outcome: 125 passing, ruff and basedpyright clean.)

---

## Phase 3 — Build the real graph

### 3.1 Dry run on a narrow range first ✅ done

```sh
uv run python -m etl build --year-from 2014 --year-to 2016 --out-version smoke
```

Confirms the three stages wire together against live QLever before committing to 102 sequential
queries.

Measured, as the baseline the full run should scale from: 65,407 rows across 3 partitions, ~7s per
query. 2,722 movies, 14,418 actors, 24,948 edges. 0 symmetry violations; `entities` keys exactly equal
the graph's nodes; cast per movie ranges 3–15 with 23% sitting at the cap; re-emit is byte-identical.
Label coverage 100% of movies, 98.5% of actors.

Two things this run surfaced, both since fixed: films had no fallback when Wikidata has an enwiki
article but no English label (`Q20856802` / "La La Land"), and `manifest.n_edges` counted interim lines
rather than distinct pairs.

### 3.2 The full run

```sh
uv run python -m etl build --year-from 1925 --year-to 2026 --out-version v1
```

102 queries with a 1s sleep between each. Two things to know:

- **Failures are non-fatal per-year.** `extract` collects failed years, keeps going, and exits non-zero
  at the end listing them. Re-running retries only those — the per-year cache makes it resumable. That's
  `extract.py:110`.
- **A `SystemExit` from extract aborts the whole `build` chain**, so transform/emit won't run on a
  partial pull. Re-run `build` until extract reports 0 failures, then it flows through.
- **Re-running a single stage needs the same dials the artifact was built with.** `--year-from` /
  `--year-to` are recorded in the manifest, so a bare `etl emit --out-version v1` uses the defaults and
  the version guard refuses it (`graph/v1 was built with different config (year_from, year_to differ)`).
  That guard is working — it stops a 3-year artifact being relabelled as a full-range one — but it is
  easy to trip when re-emitting after a fix.

### 3.3 Verify the artifact

Spot-check that the graph is *correct*, not merely *produced*:

```sh
uv run python - <<'EOF'
import collections, json
g = json.load(open('data/graph/v1/graph.json'))
m2a, a2m, ent = g['movies_to_actors'], g['actors_to_movies'], g['entities']
print('movies', len(m2a), 'actors', len(a2m), 'entities', len(ent))

bad  = sum(1 for mv, c in m2a.items() for a in c if mv not in a2m.get(a, ()))
bad += sum(1 for a, fs in a2m.items() for mv in fs if a not in m2a.get(mv, ()))
print('symmetry violations:', bad)                    # must be 0
print('entities == nodes:', set(ent) == set(m2a) | set(a2m))

unl = [q for q, e in ent.items() if e['label'] == q]
print('unlabeled:', collections.Counter(ent[q]['type'] for q in unl))

pairs = {(mv, a) for mv, c in m2a.items() for a in c}
print('n_edges matches graph:',
      json.load(open('data/graph/v1/manifest.json'))['counts']['n_edges'] == len(pairs))

sizes = [len(c) for c in m2a.values()]
print('cast/movie: min', min(sizes), 'max', max(sizes))   # must be within [min_cast, cast_cap]
EOF
```

**Expected:** 0 symmetry violations, `entities` exactly equal to the node set, `n_edges` matching, and
cast sizes inside `[min_cast, cast_cap]`. Any unlabeled **movies** is the signal to investigate — films
are anchored to an English Wikipedia article, so the article-title fallback should cover every one of
them. Unlabeled **actors** are expected and fine (no anchor applies to them); the 3-year sample ran at
1.5%, so a full-range figure in that neighbourhood is normal and a much larger one is not.

---

## TODOs — deliberately deferred, not forgotten

1. **Drop year partitioning.** `data/spike/films-all.rq` documents that QLever returns the full range in
   one query with no 60s wall. Collapsing to a single pull would delete the per-year cache, the
   failed-year accounting, and the resume logic. Not worth doing now — it would mean rewriting
   `_cache_is_valid`, `_load_rows`, and half of `test_pipeline` to save one-time runtime on a pipeline
   that runs once, and losing resume on a 102-query pull.

2. ~~**Deduplicate `edges.jsonl` across partitions.**~~ **Done** — landed with the year disambiguator,
   which promoted it from optimization to prerequisite: once an edge carries a year, a film in two
   partitions would take whichever one `emit._build_entities` wrote last. `transform._edges` now
   tracks seen film QIDs and skips a film on second sighting, so first-seen-wins over the sorted glob
   gives the earliest release year. Collects the original benefits too (~17% off the interim file and
   `emit`'s peak memory, and `TransformStats.edges` now matches `manifest.n_edges`).

3. **Incremental update path.** The graph won't be rebuilt after the initial run, but there's currently
   no "fetch year N+1 and merge into an existing artifact" command — `build` always re-emits from the
   full raw cache. That's fine and cheap (transform+emit are pure and fast over cached raw files), so
   the update cadence is: re-run `extract` for the new year, then `build`. Worth designing properly
   before the first refresh.
