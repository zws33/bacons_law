# Stage 1 — Extract (answer key)

**Goal:** pull the denormalized (film, actor) rows from Wikidata **once, politely**, and cache them per
year so the pure stages never re-hit the network.

**Consumes:** `BuildConfig` + the live WDQS endpoint.
**Produces:** `data/raw/films-<year>.json`, one per year, each a self-describing provenance wrapper.

Guide reference: [../IMPLEMENTATION_GUIDE.md](../IMPLEMENTATION_GUIDE.md) §"Stage 1";
[../EXPLORATION.md](../EXPLORATION.md) §5–6.

---

## The raw file format (the contract transform reads)

Each `films-<year>.json` is **not** a bare list — it's a wrapper carrying provenance (D6) and the filter
params that produced it (D1, so the cache can self-validate):

```json
{
  "year": 1994,
  "fetched_at": "2026-07-07T10:15:00+00:00",
  "endpoint": "https://query.wikidata.org/sparql",
  "min_sitelinks": 5,
  "require_enwiki": true,
  "row_count": 1234,
  "rows": [
    {"film": "Q25188", "film_label": "…", "film_sitelinks": 120,
     "actor": "Q38111", "actor_label": "…", "actor_sitelinks": 210},
    …
  ]
}
```

`rows[*]` is the flattened, QID-stripped denormalized row. `transform` reads only `rows`; `extract`
reads the header fields for cache validity; `emit` reads `fetched_at` (across all files) for provenance.

---

## `src/etl/sparql.py` — the thin HTTP seam

Keep this dumb and small: build the request with correct etiquette, run it, parse SPARQL-JSON bindings
into flat row dicts, strip entity URIs to QIDs. No pipeline logic here — that's what makes it easy to
mock in tests.

```python
import httpx2 as httpx  # the installed package is `httpx2`; it imports as `httpx2`, so alias it.

from etl.config import BuildConfig

_ENTITY_PREFIX = "http://www.wikidata.org/entity/"


class SparqlError(RuntimeError):
    """WDQS request failed or returned an unusable body."""


def qid_from_uri(uri: str) -> str:
    """http://www.wikidata.org/entity/Q25188 -> Q25188."""
    return uri.rsplit("/", 1)[-1]


def query(sparql_text: str, config: BuildConfig) -> list[dict]:
    """Run one SPARQL query, return flattened rows. Raises SparqlError on any failure."""
    headers = {
        "User-Agent": config.user_agent,               # REQUIRED — generic/absent agents are blocked
        "Accept": "application/sparql-results+json",
    }
    try:
        # Client-side timeout just under WDQS's ~60s server wall, so *we* fail cleanly.
        resp = httpx.post(
            config.endpoint,
            data={"query": sparql_text},               # POST form-encoded: no URL-length limit
            headers=headers,
            timeout=58,
        )
        resp.raise_for_status()
        payload = resp.json()
    except httpx.HTTPError as exc:
        raise SparqlError(f"WDQS request failed: {exc}") from exc
    except ValueError as exc:  # non-JSON body (usually an HTML error/timeout page)
        raise SparqlError(f"WDQS returned a non-JSON body: {exc}") from exc
    return _flatten(payload)


def _flatten(payload: dict) -> list[dict]:
    rows: list[dict] = []
    for b in payload["results"]["bindings"]:
        rows.append(
            {
                "film": qid_from_uri(b["film"]["value"]),
                "film_label": b["filmLabel"]["value"],
                "film_sitelinks": int(b["filmSitelinks"]["value"]),
                "actor": qid_from_uri(b["actor"]["value"]),
                "actor_label": b["actorLabel"]["value"],
                "actor_sitelinks": int(b["actorSitelinks"]["value"]),
            }
        )
    return rows
```

**Pitfalls this code already handles (don't undo them):**
- **`?film` / `?actor` come back as full URIs**, not QIDs — `qid_from_uri` strips them. Forget this and
  your join keys become URLs and nothing dedups.
- **Sitelink counts come back as *strings*** (typed literals) — `int(...)` them, or `>=` comparisons and
  the cap sort do the wrong thing.
- **POST, not GET.** Prolific years produce long query text; GET risks URL-length limits. POST
  form-encoding sidesteps it and WDQS accepts it.
- **A timeout returns an HTML page, not JSON** → `resp.json()` raises `ValueError`; we convert it to a
  clear `SparqlError` so the loop's "let it raise, then re-run" story is legible.

## `src/etl/extract.py` — the fetch loop

```python
import json
from datetime import datetime, timezone

from etl import paths, sparql
from etl.config import BuildConfig

FILM = "Q11424"
DOCUMENTARY = "Q93204"
TV_FILM = "Q506240"


def render_query(year: int, config: BuildConfig) -> str:
    """Fully templated from config (D2): min_sitelinks, the enwiki block, and the year."""
    enwiki_block = (
        "  ?article schema:about ?film ; schema:isPartOf <https://en.wikipedia.org/> .\n"
        if config.require_enwiki
        else ""
    )
    return f"""SELECT ?film ?filmLabel ?filmSitelinks ?actor ?actorLabel ?actorSitelinks WHERE {{
  ?film wdt:P31 wd:{FILM} ;
        wikibase:sitelinks ?filmSitelinks ;
        wdt:P577 ?date ;
        wdt:P161 ?actor .
  ?actor wikibase:sitelinks ?actorSitelinks .

  FILTER(?filmSitelinks >= {config.min_sitelinks})
  FILTER(YEAR(?date) = {year})
  FILTER NOT EXISTS {{ ?film wdt:P31 wd:{DOCUMENTARY} }}
  FILTER NOT EXISTS {{ ?film wdt:P31 wd:{TV_FILM} }}
{enwiki_block}  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}"""


def _cache_is_valid(year: int, config: BuildConfig) -> bool:
    """A cached year is reusable only if it was pulled with the SAME extract-time params (D1)."""
    path = paths.raw_path(year)
    if not path.exists():
        return False
    header = json.loads(path.read_text())
    return (
        header.get("min_sitelinks") == config.min_sitelinks
        and header.get("require_enwiki") == config.require_enwiki
    )


def extract(config: BuildConfig) -> None:
    paths.RAW_DIR.mkdir(parents=True, exist_ok=True)
    for year in range(config.from_year, config.to_year + 1):
        if _cache_is_valid(year, config):
            print(f"skip {year} (cached)")
            continue
        rows = sparql.query(render_query(year, config), config)  # raises on timeout → let it, re-run
        payload = {
            "year": year,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "endpoint": config.endpoint,
            "min_sitelinks": config.min_sitelinks,
            "require_enwiki": config.require_enwiki,
            "row_count": len(rows),
            "rows": rows,
        }
        _write_atomic(paths.raw_path(year), payload)
        print(f"fetched {year}: {len(rows)} rows")


def _write_atomic(path, payload: dict) -> None:
    """Write to a temp sibling then rename, so an interrupted run never leaves a half-written cache."""
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload))
    tmp.replace(path)
```

### Why each piece

- **`FILTER(YEAR(?date) = year)` is the partition key.** WDQS's ~60s wall can't pull the whole catalog
  with cast in one shot; one year at a time bounds each query to tens of thousands of edges, and makes
  the pull **resumable**.
- **`FILTER NOT EXISTS` for documentary / TV-film** enforces movies-only at the source (AGENTS "What to
  Avoid"). EXPLORATION flagged this as unmeasured — eyeball a sample once.
- **enwiki anchor + `SERVICE wikibase:label`** give recognizable titles *and* the labels the typeahead
  index needs, in one query.
- **`wikibase:sitelinks` is a materialized count**, so filtering on film sitelinks *and* pulling actor
  sitelinks (for the cap ranking) is cheap — no second query.

### Cache validity (the D1 decision, made concrete)

The whole reason `extract` reads the file header before skipping is the trap from the review: if the
filter lived only in the query and skip-were-blindly "does the file exist," then lowering
`min_sitelinks` would leave you with a stale, over-filtered cache while the manifest claimed the new
value. `_cache_is_valid` closes that: change `min_sitelinks` or `require_enwiki` and every affected year
re-fetches; change only `min_cast` / `cast_cap` (transform-time) and nothing re-fetches.

> **Alternative (not taken):** pull at a loose floor (e.g. `min_sitelinks >= 1`) and apply the real
> floor in transform. That makes the sitelink dial completely cache-free at the cost of a much larger
> raw cache. If you switch to it: drop the `>= {min_sitelinks}` from `render_query`, drop `min_sitelinks`
> from the cache header + `_cache_is_valid`, and add a `film.sitelinks >= config.min_sitelinks` filter in
> `transform.films_to_edges`. Do all three together.

### Etiquette & rate-limiting

- The descriptive `User-Agent` with contact info is **required** — this is in `config.py`, and
  `sparql.py` sends it. Absent/generic agents are blocked outright.
- Be a good citizen between requests. The loop above prints per year; if you want an explicit pause add
  `time.sleep(1)` after each successful fetch. (Left out of the core loop so tests don't sleep.)

### Fallback if a single year still times out

Prolific modern years occasionally blow the wall even partitioned. Sub-partition that year by a second
axis — two sitelink bands, or half-years — and **keep the partition key in the filename**
(`films-2018-band-hi.json`) so `transform`'s `films-*.json` glob still picks it up and QID-dedup merges
the halves. You do **not** need this to get a first end-to-end run; add it only when a year actually
fails.

---

## Verify Stage 1 in isolation

**Offline (no network):** confirm the query templates correctly and the cache logic is sound without
fetching anything.

```bash
uv run python -c "
from etl.config import BuildConfig
from etl.extract import render_query
q = render_query(1994, BuildConfig())
assert 'YEAR(?date) = 1994' in q
assert '?filmSitelinks >= 5' in q
assert 'en.wikipedia.org' in q          # require_enwiki=True
q2 = render_query(1994, BuildConfig(require_enwiki=False))
assert 'en.wikipedia.org' not in q2
print('render_query OK')
"
```

**Live smoke (opt-in, one year):** proves the endpoint, headers, and parser agree with reality.

```bash
uv run python -c "
from etl.config import BuildConfig
from etl.extract import render_query
from etl import sparql
rows = sparql.query(render_query(1994, BuildConfig()), BuildConfig())
print('rows:', len(rows)); print(rows[0])
assert rows[0]['film'].startswith('Q') and isinstance(rows[0]['actor_sitelinks'], int)
"
```

Expect a few thousand rows for 1994 and a first row whose `film`/`actor` are bare QIDs and whose
sitelink fields are `int`. If `film` looks like a URL, `qid_from_uri` isn't wired in; if sitelinks are
strings, you dropped the `int(...)`.
