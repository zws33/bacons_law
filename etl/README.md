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
