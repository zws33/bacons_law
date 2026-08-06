# ETL — agent operating rules (offline Python)

Scope: this directory is the **offline graph build** — a self-contained Python toolchain
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
- **Truncation by `cast_cap` is itself a notability filter.** Because ranking is by the actor's own
  sitelinks, an actor who appears in several films and survives the cap in none of them is thereby
  demonstrated to be obscure — not merely unlucky. This is measured, not assumed: cap-truncated
  actors are *less* notable than genuine one-credit actors on every percentile
  ([ADR 019](../docs/DECISIONS.md)). The practical consequence is that **"cap rescue" — restoring a
  truncated actor's next-best edge so they are not left with a single credit — was measured and
  rejected.** Do not re-propose it without new evidence; it repairs a population more obscure than
  the one it leaves behind.
- **`min_sitelinks` gates FILMS, not actors.** `extract.py` filters `?filmSitelinks` only;
  `?actorSitelinks` is selected and never filtered. Actors therefore enter at any notability, and
  in a film with `min_cast` cast members all of them survive regardless of who they are. This is why
  45.9% of actor nodes in `v1` are degree-1 — a known and **accepted** property, not an oversight
  ([ADR 019](../docs/DECISIONS.md)).
- **Filter = enwiki ∩ ≥`min_sitelinks` ∩ ≥`min_cast` cast.** The enwiki anchor is unconditional in the
  query and `min_sitelinks` is applied at **extract** time (baked into the raw cache); `min_cast` /
  `cast_cap` are **transform**-time dials you retune often.
- **Artifact keys are Wikidata QIDs (strings).** This is the contract the server validates against.
  If a consuming engine wants some other ID type, that mapping is a **loader-side** concern — do
  **not** pre-map QIDs to ints here. (The current Kotlin `:core` declares `Set<Int>`, left over from
  the dropped TMDB source; that signature is provisional and does not bind this pipeline.)
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
- **Movies only:** exclude documentary (`Q93204`) and TV-film (`Q506240`) at extract. These are exact
  `P31` checks, so they only catch what an editor tagged — a documentary typed solely as `film` gets
  through, and miniseries (`Q1259759`) is a different class from TV-film. Known leak, deferred:
  [#19](https://github.com/zws33/bacons_law/issues/19).
- **Nothing constrains the type of the `P161` object.** Whatever a film points at becomes an actor
  node, so a handful of films are keyed as actors. Also [#19](https://github.com/zws33/bacons_law/issues/19).
- **Year partitioning is a retained choice, not a requirement.** It existed to fit under the WDQS 60s
  wall, which QLever doesn't have. It stays because it keeps the raw cache resumable and each
  response small enough for non-streaming JSON parsing. Don't collapse it to a single query as a
  cleanup.

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

- **`README.md`** — the pipeline at a glance, the current artifact's shape, the verification script,
  and known follow-ons (deferred work lives there, not here — this file is operating rules only).
- Config contract: `src/etl/config.py`.

Plans and guides are deleted once the code catches up; the facts worth keeping are inlined above and
git history holds the rest. That has already happened to `IMPLEMENTATION_GUIDE.md`,
`QLEVER_MIGRATION_PLAN.md`, `YEAR_PLAN.md`, the staged reference implementations (`docs/00–04`), and
`EXPLORATION.md` — the last of which characterized the Wikidata source to pick the dials
(`min_sitelinks`, `min_cast`, `cast_cap`, ranking cast by actor sitelinks rather than billing order).
Those dials are now settled and recorded above, so the characterization behind them is no longer
needed.
