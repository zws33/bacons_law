# Plan — release year as a typeahead disambiguator

**Goal:** `graph.json`'s `entities` index carries a release year for every movie, so Phase 4 typeahead
can render "The Mummy (1999)" and let the player pick the film they meant.

Delete this file once the change lands, per the convention that plans go stale the moment the code
catches up (`AGENTS.md`).

---

## Why this is cheap

The year is **already in the raw cache**. `extract` stamps `CachePayload.year` on every partition, and
`FILTER(YEAR(?date) = {year})` means that year *is* a publication year of every film in the partition.
`transform._load_rows()` currently validates the payload and then yields only `data.rows`, dropping the
one field we need.

So this is a **transform + emit change over the existing cache** — no query change, no `QUERY_VERSION`
bump, no re-pull. The three cached partitions in `data/raw/` stay valid.

(An earlier read of this said year required adding `?date` to the SELECT and re-pulling all 102 years.
That was wrong: it missed that the partition key already encodes the answer.)

## The problem it drags in

`P577` is multi-valued, so a film with a festival premiere in one year and a wide release in the next
lands in **both** partitions and writes its edges twice (407 films / 4,282 lines — ~17% — in the 3-year
sample). Today that is harmless: `emit._build_adjacency` dedupes through sets and `manifest.n_edges`
counts distinct pairs.

It stops being harmless the moment an edge carries a year. `emit._build_entities` assigns
`entities[e.movie]` in a loop, so **last write wins** — a film in two partitions would silently take
the *later* year, and which year that is depends on partition iteration order rather than on the film.

The fix is the one already written down as deferred TODO #2 in `REPAIR_PLAN.md`: dedupe films across
partitions in `transform`, first-seen-wins. Because `_load_rows()` sorts the glob, partitions arrive
oldest-first, so **first-seen-wins means earliest release year wins** — deterministic, and the
conventional answer for "what year is this film."

That TODO is therefore promoted from optimization to prerequisite. Landing it here also collects its
original benefits: ~17% off the interim file, the same off `emit`'s peak memory, and
`TransformStats.edges` stops overstating the graph (it currently counts interim lines, so the number
the CLI prints after `transform` disagrees with `manifest.n_edges`).

Dropping repeat sightings is safe because the cast comes from `wdt:P161`, which is date-independent —
the repeat partition carries the same rows.

## Changes

### `models.py`

- `Edge` gains `movie_year: int`. Field order keeps the movie fields together
  (`movie, movie_label, movie_year, actor, actor_label`); `emit` reads back with `Edge(**r)`, so order
  is cosmetic.
- New `Entity` TypedDict — `label: str`, `type: str`, `year: NotRequired[int]` — replacing the
  anonymous `dict[str, str]`. `year` is **absent for actors**, not null: actors have no release year,
  and omitting it keeps ~300k null fields out of the artifact. A Kotlin loader reads it as `Int?`.
- `Film` is left alone. Every film in a partition shares that partition's year, so the year is a
  parameter of the batch, not a property to thread through the per-film accumulator.

### `transform.py`

- `_load_rows()` yields the whole `CachePayload` instead of `.rows`, and gets the return annotation it
  was missing. Callers take `.year` and `.rows`. Trusting the payload's `year` field over the filename
  is deliberate — it is the validated record.
- `_build_edge_list(rows, year, min_cast, cast_cap)` stamps `movie_year=year` on every edge it builds.
  Stays a pure function of its arguments.
- `_edges()` carries the cross-partition `seen` set: rows for an already-seen film are filtered out
  before `_build_edge_list`, then every film QID in the partition joins `seen` — including films the
  `min_cast` gate dropped, which would be dropped identically next time anyway.

### `emit.py`

- `_build_entities` writes `"year": e.movie_year` on movie entries only.
- `SCHEMA_VERSION` 1 → 2. The artifact's shape changed; that is what the field is for. Nothing consumes
  the artifact yet, so there is no migration to write.

### Tests

- `test_transform.py` — `_build_edge_list` call sites take `year`; new cases for the year landing on
  the edge, and for the cross-partition film being emitted once at its earliest year.
- `test_emit.py` — `_edge()` helper carries a year; `_build_entities` asserts year present on movies
  and absent on actors.
- `test_pipeline.py` — the fake catalog gets a film released in both 1994 and 1995, so the end-to-end
  run exercises dedupe + earliest-year through real stages.
- `test_cli.py` — `_edge()` helper only.

## Out of scope

Sitelink count in `entities` (a ranking signal, not a disambiguator — separate call), and the
incremental-update path.
