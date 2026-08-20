# etl — the offline graph build

Builds a actor↔movie graph artifact. Source is CC0 Wikidata over SPARQL (QLever).

```sh
uv sync
uv run python -m etl build --year-from 1925 --year-to 2026 --out-version v2
```

Three stages with a disk cache between each, individually invokable — `extract` is slow and
network-bound, `transform` and `emit` are pure and fast.

| Stage | Reads | Writes |
|---|---|---|
| `extract` | QLever | `data/raw/films-YYYY.json` |
| `transform` | `data/raw/` | `data/interim/edges.jsonl` |
| `emit` | `data/interim/edges.jsonl` | `data/graph/<version>/{graph,manifest}.json` |

`graph.json` holds `movies_to_actors` and `actors_to_movies` (QID → sorted QIDs, the O(1)
set-membership check the server validates moves against) plus `entities` (QID → `{label, type,
sitelinks}`, with `year` on movies). Labels and years are what a typeahead renders; `sitelinks` is
what it ranks on

`data/` is gitignored and a full pull is ~100 sequential queries against a best-effort third-party
endpoint — **back up `data/raw/` once you have it.**
