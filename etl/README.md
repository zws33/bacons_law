# etl — the offline graph build

Builds the versioned actor↔movie graph artifact that the Bacon's Law server loads read-only at boot.
Source is CC0 Wikidata over SPARQL (QLever). Runs **offline** — it is never in the request path, and
there is no API key.

```sh
uv sync
uv run python -m etl build --year-from 1925 --year-to 2026 --out-version v1
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
set-membership check the server validates moves against) plus `entities` (QID → `{label, type}`, with
`year` on movies for typeahead disambiguation).

`data/` is gitignored and a full pull is ~100 sequential queries against a best-effort third-party
endpoint — **back up `data/raw/` once you have it.**

Development commands and the decisions behind the pipeline are in [AGENTS.md](AGENTS.md).

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
