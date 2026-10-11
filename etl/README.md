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

## Corpus dials

Defaults in [`src/etl/config.py`](src/etl/config.py), each overridable on the `build` command. They
decide what the graph contains, so they decide what counts as a legal move for the round engine.

| Dial | Default | CLI | Effect |
|---|---|---|---|
| `min_sitelinks` | 5 | `--min-sitelinks` | Drops obscure entities below this Wikidata sitelink count |
| `min_cast` | 3 | `--min-cast` | Drops a film whose cast is smaller than this |
| `cast_cap` | 15 | `--cap` | Keeps only the top-N billed actors per film |

`cast_cap` is why a real but low-billed cast member is not a valid move — the edge is absent from the
artifact. Expect the argument to recur in playtests.

`data/` is gitignored and a full pull is ~100 sequential queries against a best-effort third-party
endpoint — **back up `data/raw/` once you have it.**
