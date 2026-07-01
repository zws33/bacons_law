# ETL Implementation Guide — Phase 1 graph build

> **What this is.** A teaching-oriented build guide for this `etl/` pipeline, written so you implement
> it by hand. It gives instructions, the reasoning behind each decision, and illustrative snippets for
> the fiddly parts (SPARQL text, HTTP etiquette, dict-of-sets indexing) — but you write the function
> bodies. Concepts are explained inline where they first matter. Not a spec to copy; a map to build
> from. Pairs with [EXPLORATION.md](./EXPLORATION.md) (the source characterization) and the repo docs.

---

## Context

The server validates every move with an O(1) set-membership check against a precomputed actor↔movie
graph held in RAM (ADR 009, [../docs/CASE_STUDY.md](../docs/CASE_STUDY.md) §2–3). That graph is a
**build-time input**, not a request-path dependency — it's produced once, offline, by this ETL and
loaded read-only at boot. Phase 1's job ([../ROADMAP.md](../ROADMAP.md)) is exactly: produce a
**reproducible, versioned artifact** — the bipartite graph plus a typeahead entity index — from **CC0
Wikidata** (ADR 010), in a **self-contained Python toolchain** (`uv`/`ruff`, ADR 011) with no coupling
to the Gradle project.

The reconnaissance is done ([EXPLORATION.md](./EXPLORATION.md)). Its plan-editing findings drive this
design:

- **Billing order (`P1545`) is ~8% populated → unusable.** "Top-N *billed*" is dead; rank cast by the
  **actor's own sitelink count** instead (a signal we already pull; it also tames blockbuster
  super-connectors — the gameplay knob).
- **Scale is a non-issue** (~600k edges, tens of MB) → **JSON is fine**; the cap's job is gameplay +
  policy, not size.
- **Sitelink count is language-agnostic** → anchor on **enwiki ∩ ≥N sitelinks ∩ ≥3 cast** for an
  English audience.
- **Only truthy `wdt:` queries scale** under WDQS's hard 60s wall; `p:`/`pq:` (statement/qualifier)
  queries time out. We stay on the fast path and **partition by release year**, caching raw results to
  disk so the transform stage never re-hits Wikidata.

**Scope decision (assumption):** artifact = **graph + typeahead entity index**. The labels needed for
typeahead ride along on the same query via the label service, so pulling them now is nearly free and
satisfies Phase 1's "done when." If you'd rather defer search, drop the `entities` map from Stage 3 and
the label columns from Stage 1 — nothing else changes.

---

## Architecture: a three-stage pipeline with a disk seam

```
Wikidata (SPARQL)                data/raw/                data/interim/              graph/<version>/
   │  extract (I/O, slow)   →   films-1970.json     →    edges.jsonl        →       manifest.json
   │  partitioned by year        films-1971.json          (capped edge list)         graph.json
   │  cached, resumable          …                        transform (pure)           emit (pure)
```

**Why stage it.** The three stages have different *natures*, and separating them by a **cached seam on
disk** is the whole point:

- **Extract is slow, non-deterministic, and rate-limited** (network I/O against a shared public
  endpoint). You want to run it *rarely* and never accidentally hammer Wikidata.
- **Transform and emit are pure and fast** (in-memory data-wrangling). You'll iterate on these dozens
  of times while tuning the cap and threshold.

If they were one script, every tweak to the cap would re-download the internet. With a disk seam, the
raw pull is a one-time cost; transform reads `data/raw/*.json` and runs in seconds. This is the
**offline-batch idempotency** pattern: each stage is a pure function of its input files, so re-running
is cheap and reproducible. It's also what EXPLORATION §5 explicitly tells you to do ("cache raw results
to disk so the transform stage never re-hits Wikidata").

**Two data shapes you'll move between (worth naming):**

- **Denormalized edge rows** — what SPARQL returns: one row per (film, actor) pair, film/actor labels
  and sitelink counts repeated. Easy to stream and cache; wasteful to reason about.
- **Adjacency maps** — the artifact: `movie → set(actors)`, `actor → set(movies)`. O(1) lookup, no
  repetition. The transform's job is to fold the first into the second.

---

## Stage 0 — Project scaffolding

Goal: a self-contained `etl/` project that a fresh clone can build from scratch.

1. **`uv` for env + deps.** `uv init` in `etl/`, then `uv add httpx` (runtime) and
   `uv add --dev pytest ruff` (dev). `uv` gives you a locked, reproducible environment without the
   virtualenv ceremony — *reproducibility* is a first-class goal here, and the lockfile is part of it.
2. **`ruff` for lint + format.** Configure in `pyproject.toml`; 4-space indent is already set by the
   root `.editorconfig` (Python 4). One tool, fast, no Black/isort/flake8 zoo.
3. **Package layout** — a real package so stages import cleanly and are unit-testable:
   ```
   etl/
     pyproject.toml
     src/etl/
       __init__.py
       config.py        # frozen params: thresholds, cap N, paths, endpoint, User-Agent
       extract.py       # Stage 1 — SPARQL + disk cache
       transform.py     # Stage 2 — filter, cap, fold to edges  (PURE, heavily tested)
       emit.py          # Stage 3 — invert, build maps + index, write versioned artifact
       sparql.py        # thin SPARQL-over-HTTP client (etiquette lives here)
       __main__.py      # CLI: `python -m etl build --year-from 1900 --cap 15 ...`
     tests/
       test_transform.py
       fixtures/…
     data/              # gitignored: raw/ and interim/ caches
   ```
4. **`config.py` as the single source of tunable truth.** The threshold and cap are *gameplay dials*
   (CASE_STUDY §3), so make them parameters, not magic numbers scattered in code. A frozen dataclass is
   enough:
   ```python
   @dataclass(frozen=True)
   class BuildConfig:
       min_sitelinks: int = 5      # notability floor (EXPLORATION: 5 → ~68k films)
       min_cast: int = 3           # min-cast floor (drops ~25% dead-weight films)
       cast_cap: int = 15          # top-N by ACTOR sitelink count (not billing order)
       require_enwiki: bool = True # English-audience recognizability anchor
       user_agent: str = "bacons-law-etl/0.1 (zach.smith33@gmail.com)"
       endpoint: str = "https://query.wikidata.org/sparql"
   ```
   Every one of these appears later in the artifact manifest — that's how a build becomes *reproducible
   and self-describing*.

---

## Stage 1 — Extract (SPARQL → `data/raw/*.json`)

Goal: pull the denormalized edge rows once, politely, and cache them per year.

### The query (illustrative — adapt from EXPLORATION §6)

Stay entirely on **truthy `wdt:`** (the one materialized hop; fast) — never `p:`/`pq:` (reified
statements; time out). One query per release-year partition:

```sparql
SELECT ?film ?filmLabel ?filmSitelinks ?actor ?actorLabel ?actorSitelinks WHERE {
  ?film wdt:P31 wd:Q11424 ;               # instance of: film
        wikibase:sitelinks ?filmSitelinks ;
        wdt:P577 ?date ;                   # publication date → partition key
        wdt:P161 ?actor .                  # cast member (the edge)
  ?actor wikibase:sitelinks ?actorSitelinks .

  FILTER(?filmSitelinks >= 5)
  FILTER(YEAR(?date) = 1994)               # ← the partition; substitute per run
  FILTER NOT EXISTS { ?film wdt:P31 wd:Q93204 }   # exclude documentary
  FILTER NOT EXISTS { ?film wdt:P31 wd:Q506240 }  # exclude TV film

  # enwiki anchor (recognizability): require an English Wikipedia article
  ?article schema:about ?film ; schema:isPartOf <https://en.wikipedia.org/> .

  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

**Why each piece:**
- `wikibase:sitelinks` is a *materialized* count (ontology-level), so filtering/pulling it is cheap —
  this is what lets us both filter on notability *and* rank cast by actor notability without a second
  query.
- `FILTER(YEAR(?date) = …)` is the **partition key**. WDQS has a hard ~60s server timeout; a single
  pull of the whole catalog with cast blows past it. Slicing by year bounds each query to tens of
  thousands of edges — comfortably under the wall — and makes the pull **resumable** (see below).
- `FILTER NOT EXISTS` for `Q93204`/`Q506240` enforces the **movies-only** project constraint at the
  source (AGENTS "What to Avoid"). EXPLORATION flagged this as unmeasured — expect to eyeball a sample.
- The **enwiki anchor** + `SERVICE wikibase:label` give recognizable titles *and* the labels the
  typeahead index needs, in one shot.

### The client and the loop

- **Etiquette is not optional** (`sparql.py`): a descriptive `User-Agent` with contact info is
  **required** — generic/absent agents are blocked outright. Set `Accept:
  application/sparql-results+json`. Use a client-side timeout just under WDQS's server limit
  (`httpx.get(..., timeout=58)`) so *you* fail cleanly instead of eating an opaque upstream 500.
- **Resumability = skip-if-cached.** Iterate years; before each request check whether
  `data/raw/films-<year>.json` already exists and skip if so. This makes an interrupted pull safe to
  re-run (idempotent), and means a threshold change that widens the catalog only fetches the *new*
  slices. Illustrative:
  ```python
  for year in range(cfg.year_from, cfg.year_to + 1):
      path = raw_dir / f"films-{year}.json"
      if path.exists():
          continue
      rows = sparql.query(render_query(year, cfg))   # raises on timeout → let it, then rerun
      path.write_text(json.dumps(rows))
      time.sleep(1)                                    # be a good citizen; don't burst
  ```
- **Fallback if a year still times out** (prolific modern years): sub-partition — split that year by a
  second axis (e.g. two sitelink bands, or half-years). Keep the partition key in the filename so the
  cache stays coherent.

**Concept — why cache the *raw* rows, not the cleaned graph:** the raw pull is your expensive,
non-reproducible-on-demand resource (Wikidata changes daily; the endpoint is shared). Freezing it to
disk makes every downstream run deterministic *and* offline. The date of this pull becomes provenance
you record in the manifest.

---

## Stage 2 — Transform (`data/raw/*.json` → `data/interim/edges.jsonl`)

Goal: fold denormalized rows into a **capped, deterministic** edge list. **This stage is pure — no
I/O beyond reading its input files — so it's where your unit tests live.**

Steps, in order:

1. **Load + group by film.** Read every `films-*.json`, accumulate per-film cast: `film_qid →
   {label, sitelinks, cast: {actor_qid: (label, actor_sitelinks)}}`. Use a dict keyed by QID so
   duplicate rows across partitions collapse naturally (dedup for free).
2. **Apply the min-cast floor.** Drop any film with `< cfg.min_cast` distinct cast members. EXPLORATION:
   ~25% of "notable" films have <3 cast; the notability filter alone is insufficient, so this floor is
   *required*, not optional.
3. **Apply the cast-depth cap — the load-bearing step.** For each film, **sort its cast by actor
   sitelink count descending, take the top `cfg.cast_cap`.** This is the EXPLORATION pivot: billing
   order is unusable, so actor notability *is* the ranking. Three jobs in one lever (CASE_STUDY §3):
   gameplay difficulty, the policy definition of "appeared in," and (here, secondarily) size.
   - **Determinism matters:** ties in sitelink count must break deterministically or two builds of the
     same input differ. Sort with a stable tiebreaker — `key=(-actor_sitelinks, actor_qid)` — so the
     artifact is byte-reproducible and diffable. (You want to be able to `diff` two builds and see only
     *real* catalog changes.)
4. **Emit the capped edge list** to `data/interim/edges.jsonl` — one `{"movie": qid, "actor": qid}` (+
   labels) per line. JSONL because it streams and appends cleanly; this interim file is the single
   source of truth the emit stage inverts.

Illustrative core of step 3:
```python
def cap_cast(cast: dict[str, Actor], n: int) -> list[str]:
    return [a.qid for a in sorted(
        cast.values(), key=lambda a: (-a.sitelinks, a.qid))[:n]]
```

**Why keep transform pure:** the CASE_STUDY's whole thesis is "move hard work offline and isolate pure
logic." The cap/floor rules are exactly the policy you'll want to *trust* and *tune*. A pure function
of `(rows, config) → edges` is trivially unit-testable and re-runnable, and it mirrors the `:core`
purity discipline on the Kotlin side.

---

## Stage 3 — Emit (`data/interim/edges.jsonl` → `graph/<version>/`)

Goal: build both adjacency directions + the entity index, and write a **versioned, self-describing**
artifact. Also pure.

1. **Invert once to guarantee symmetry.** Build `movie → set(actor)` from the edge list, then derive
   `actor → set(movie)` **by inverting that same map** — do not build the two independently. EXPLORATION
   §4.3: "index both directions so the graph can never be asymmetric." Deriving one from the other makes
   asymmetry *structurally impossible* rather than a bug you hope to avoid.
   ```python
   movie_to_actors: dict[str, set[str]] = defaultdict(set)
   for e in edges:
       movie_to_actors[e.movie].add(e.actor)
   actor_to_movies: dict[str, set[str]] = defaultdict(set)
   for movie, actors in movie_to_actors.items():
       for a in actors:
           actor_to_movies[a].add(movie)
   ```
2. **Build the typeahead entity index:** `qid → {"label": str, "type": "movie"|"actor"}` from the
   labels carried on the edges. This is what Phase 4 search resolves names against (names → entity IDs
   at the boundary — CASE_STUDY §3). *(Omit this map if you chose to defer search.)*
3. **Serialize sets as sorted lists.** JSON has no set type; sort on write so output is deterministic
   and diffable. The Kotlin loader reads lists back into `Set`s — sorting is purely for build hygiene.
4. **Keys are Wikidata QIDs (strings).** Provenance-inline and stable (ADR 010). The engine's
   `castIds: Set<Int>` contract is a **loader-side** concern — the Kotlin loader assigns its own int
   IDs; the artifact stays QID-keyed. Don't pre-map to ints here.
5. **Write a versioned directory with a manifest.** This is what makes it an *artifact* rather than a
   dump:
   ```
   graph/v1/
     manifest.json   # schema_version, source="wikidata", query_date, config params, counts
     graph.json      # { "movies": {qid: [actorQid,…]}, "actors": {qid: [movieQid,…]},
                     #   "entities": {qid: {"label","type"}} }
   ```
   The manifest records the **exact parameters** (`min_sitelinks`, `min_cast`, `cast_cap`, enwiki flag)
   and **counts** (`n_movies`, `n_actors`, `n_edges`) plus the raw-pull date. Why: the server loads *a
   specific version*; a build is reproducible only if it says what went into it; and the params are the
   gameplay dial, so they must travel *with* the data. Versioning the directory means a re-tuned build
   is a new `v2/` beside `v1/`, not an in-place mutation.

---

## Testing strategy

The value is concentrated in the **pure** stages — test those hard, keep extract thin.

- **`transform.py` unit tests** (the important ones), against tiny hand-built row fixtures:
  - cap keeps exactly the top-N by actor sitelinks, and **ties break by QID** (determinism);
  - min-cast floor drops sub-floor films and keeps at-floor films (boundary test);
  - duplicate rows across partitions collapse to one edge.
- **Emit invariant test:** the **symmetry property** — for every `actor ∈ movie_to_actors[m]`, assert
  `m ∈ actor_to_movies[actor]` (and vice versa). This is a cheap property test that guards the one
  invariant a graph bug would violate.
- **Determinism test:** run emit twice on the same interim file; assert byte-identical output.
- **Extract:** keep `sparql.py` a thin seam and either mock the HTTP call or run a single-year **live
  smoke test** (skippable/marked) that asserts the row shape — don't put the network in the fast suite.

Run with `uv run pytest`. Lint/format with `uv run ruff check` / `uv run ruff format`.

---

## Verification — Phase 1 "done when"

ROADMAP: *"a documented offline run produces a loadable, versioned artifact from scratch."* Concretely:

1. From a clean `etl/`, `uv sync`, then `uv run python -m etl build` (with default config) completes:
   pulls raw slices → writes `data/raw/*.json` → `data/interim/edges.jsonl` → `graph/v1/`.
2. `graph/v1/manifest.json` exists and its `n_movies` lands in the ~50k ballpark and `n_edges` in the
   hundreds of thousands (EXPLORATION sanity numbers: ~51k usable films, ~593k raw edges pre-cap).
3. **Symmetry + load check** (write a 15-line throwaway script): load `graph.json`, assert every
   `movie→actor` edge has its inverse, and spot-check a known chain by QID — e.g. *Inception* (`Q25188`)
   contains DiCaprio (`Q38111`), and DiCaprio's films contain *Titanic* (`Q44578`). This proves the
   O(1) lookup the server will do is correct against real data.
4. Re-run the pipeline; confirm the raw cache is reused (no new network calls) and `graph/v1` is
   byte-identical — proving reproducibility.
5. `uv run pytest` green; `uv run ruff check` clean.

---

## Concepts referenced (for the learning goal)

- **Bipartite graph / adjacency maps** — two node sets (movies, actors), edges only between sets; the
  game is a walk alternating sets; validation is one set-membership check (CASE_STUDY §3).
- **Offline/online seam** — the polyglot split ADR 011 blesses: Python offline, Kotlin online. This ETL
  lives entirely on the offline side; it never touches the request path.
- **Idempotent, resumable batch** — each stage is a pure function of its input files; a disk cache
  makes re-runs cheap and the whole build reproducible.
- **Deterministic builds** — stable sorts + sorted serialization → byte-reproducible, diffable
  artifacts; a prerequisite for trusting "same input, same graph."
- **Provenance keys** — QIDs are both the join key and the record of where a fact came from (CASE_STUDY
  §4: provenance, not formatting, is what binds; CC0 removes the obligation entirely).

---

## Deliberately out of scope (defer)

- **Wikidata dumps path** — SPARQL-partitioned pull is enough at this scale (EXPLORATION §5); dumps buy
  completeness/reproducibility at a size cost. Revisit only if the endpoint becomes a bottleneck.
- **The MediaWiki Action API entity-detail fetch** — only needed if you later want per-entity fields the
  SPARQL rows don't carry. Not required for the graph.
- **`P1545` as a real signal** — ~8% coverage; at most a rare tiebreaker, and we already tiebreak on QID.
- **Kotlin loader / QID→Int mapping** — that's Phase 2, on the server side, not this artifact's concern.
