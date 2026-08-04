# ETL — agent operating rules (offline Python)

Scope: this directory is the **Phase 1 offline graph build** — a self-contained Python toolchain
(`uv` + `ruff`, Python 3.14) with no coupling to the Kotlin project. It runs **offline**, produces the
versioned graph artifact the server loads at boot, and is **never** in the request path. (The root
`AGENTS.md` still applies; this file adds the ETL-specific focus so a session here doesn't have to
reason about the whole backend.)

## Build & test (run from `etl/`)

- `uv sync` — install locked deps
- `uv run python -m etl build [--year-from 1900 --year-to 2026 --cap 15 --out-version v1]`
- `uv run python -m etl <extract|transform|emit>` — one stage at a time; the disk seam is the point
- `uv run pytest` — unit tests (concentrate them on the pure stages)
- `uv run ruff check` / `uv run ruff format`

The artifact flag is `--out-version`, not `--version`: argparse reserves the latter, and the manifest
already has an unrelated `schema_version`.

## Pipeline shape — three stages, a disk cache between each

`extract` (SPARQL → `data/raw/*.json`; I/O, cached, resumable) → `transform` (raw →
`data/interim/edges.jsonl`; **pure**) → `emit` (edges → `data/graph/<version>/`; **pure**).

Extract is the only networked stage — run it rarely. transform/emit are pure and fast; that's where
the tests and the tuning live. Retuning a gameplay dial should cost a `transform && emit`, never a
re-pull.

## Load-bearing facts (don't relitigate)

- **Source is CC0 Wikidata over SPARQL. No TMDB, no API key.** The endpoint is **QLever**
  (`https://qlever.dev/api/wikidata`), a third-party index over the same CC0 data — not the official
  WDQS. That choice is forced: WDQS could not serve the full 1900–2026 range at any decomposition —
  a single year with labels exceeded its 60s wall (measured). QLever serves a labelled year in ~7s.
- **QLever requires explicit `PREFIX` declarations.** WDQS injects `wd:`, `wdt:`, `wikibase:`, and
  `schema:` silently; QLever has no defaults and rejects the query without them. This is the most
  likely cause of a confusing first failure.
- **`SERVICE wikibase:label` does not exist on QLever** — it's a Wikibase extension. Labels come from
  `OPTIONAL { ?x rdfs:label ?l . FILTER(LANG(?l) = "en") }`. `OPTIONAL`, so an entity with no English
  label still produces its edge; unbound variables are **absent** from the JSON binding object, not
  null.
- **Stay on truthy `wdt:`.** Not for speed now — for semantics. `p:`/`pq:` reified statements would
  only buy qualifiers we've already established are unusable (below).
- **Billing order (`P1545`) is ~8% populated → unusable.** Rank each film's cast by the **actor's own
  sitelink count** and take top-N (`cast_cap`). This lever is gameplay + policy, not a size hack.
- **Filter = enwiki ∩ ≥`min_sitelinks` ∩ ≥`min_cast` cast.** The enwiki anchor is unconditional in the
  query and `min_sitelinks` is applied at **extract** time (baked into the raw cache); `min_cast` /
  `cast_cap` are **transform**-time dials you retune often.
- **Artifact keys are Wikidata QIDs (strings).** The engine's `castIds: Set<Int>` contract is a
  *loader-side* (Phase 2, Kotlin) concern — do **not** pre-map QIDs to ints here.
- **A movie's release year comes from its partition, not a second query.** `FILTER(YEAR(?date) = N)`
  means the partition key *is* a publication year of every film in the file, so `entities` gets its
  year from `CachePayload.year` for free. Don't add `?date` to the SELECT to get it. Movies carry
  `year`; actors have no such key (absent, not null).
- **A film can legitimately appear in two partitions** — `P577` is multi-valued, so a festival
  premiere and a wide release fall in different years. `transform` emits each film from the **first**
  partition it appears in; since `_load_rows` sorts, that is the earliest release year. Don't "fix"
  this by taking the latest, and don't remove the dedupe — the year would become order-dependent.
- **Determinism is a requirement:** stable sort (`key=(-sitelinks, qid)`) + sorted serialization → a
  byte-reproducible, diffable artifact. Precisely: **the same raw cache must produce the same
  artifact.** It is not "the same query produces the same bytes" — the live index drifts ~0.008%/day,
  so two pulls days apart legitimately differ. Reproducibility lives at the disk seam, not at the
  endpoint.
- **Movies only:** exclude documentary (`Q93204`) and TV-film (`Q506240`) at extract.
- **Year partitioning is a retained choice, not a requirement.** It existed to fit under the WDQS 60s
  wall, which QLever doesn't have. It stays because it keeps the raw cache resumable and each
  response small enough for non-streaming JSON parsing. Collapsing to one query is a documented
  follow-on, not a bug to fix.

## The one architectural reason this pipeline exists

The server validates every move with an **O(1) in-memory set-membership check** against this graph,
loaded read-only at boot — no per-turn API call. So this pipeline's entire job is to produce a
**correct, reproducible, deterministic** bipartite artifact. Everything above is downstream of that.

## Operational note

QLever is a third-party, best-effort service with no SLA, and **there is no working fallback that
produces a complete graph** — WDQS can't serve the volume, and the alternative is a 150GB dump
pipeline. `data/` is gitignored, so once a full pull lands, **back up `data/raw/` and
`data/graph/<version>/` off this machine.** A raw cache you already hold is the difference between an
outage being an inconvenience and being a rebuild from dumps.

## Docs — open the right one, only when you need it (context hygiene)

- **`REPAIR_PLAN.md`** — the in-flight work: finishing the QLever migration and running the first full
  build. Start here while it exists; delete it once the graph is built.
- **`EXPLORATION.md`** — the Wikidata source characterization (the numbers behind the decisions).
  Still accurate; the spike independently corroborated its ~68k-films-at-`min_sitelinks=5` figure.
- Config contract: `src/etl/config.py`.

`IMPLEMENTATION_GUIDE.md` and `QLEVER_MIGRATION_PLAN.md` were deleted once the migration they described
landed — a build-it-by-hand guide and a migration plan both go stale the moment the code catches up.
The facts worth keeping from them are inlined above. Git history holds the rest, as it does for the
staged reference implementations (`docs/00–04`) removed earlier.
