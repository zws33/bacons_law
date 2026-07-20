# ETL — agent operating rules (offline Python)

Scope: this directory is the **Phase 1 offline graph build** — a self-contained Python toolchain
(`uv` + `ruff`, Python 3.14) with no coupling to the Kotlin project. It runs **offline**, produces the
versioned graph artifact the server loads at boot, and is **never** in the request path. (The root
`AGENTS.md` still applies; this file adds the ETL-specific focus so a session here doesn't have to reason
about the whole backend.)

## Build & test (run from `etl/`)

- `uv sync` — install locked deps
- `uv run python -m etl build [--year-from 1900 --year-to 2026 --cap 15 --version v1]`
- `uv run pytest` — unit tests (concentrate them on the pure stages)
- `uv run ruff check` / `uv run ruff format`

## Pipeline shape — three stages, a disk cache between each

`extract` (SPARQL → `data/raw/*.json`; I/O, cached, resumable) → `transform` (raw → `data/interim/edges.jsonl`; **pure**) → `emit` (edges → `graph/<version>/`; **pure**).

Extract is slow and networked — run it rarely. transform/emit are pure and fast — that's where the tests
and the tuning live.

## Load-bearing facts (don't relitigate)

- **Source is CC0 Wikidata over SPARQL. No TMDB, no API key.** Stay on truthy `wdt:` (fast); `p:`/`pq:`
  (reified statements/qualifiers) time out at the ~60s WDQS wall. Partition by release year and cache raw
  to disk so transform never re-hits the network.
- **Billing order (`P1545`) is ~8% populated → unusable.** Rank each film's cast by the **actor's own
  sitelink count** and take top-N (`cast_cap`). This lever is gameplay + policy, not a size hack.
- **Filter = enwiki ∩ ≥`min_sitelinks` ∩ ≥`min_cast` cast.** `min_sitelinks` / `require_enwiki` are
  applied at **extract** time (baked into the raw cache); `min_cast` / `cast_cap` are **transform**-time
  dials you retune often.
- **Artifact keys are Wikidata QIDs (strings).** The engine's `castIds: Set<Int>` contract is a
  *loader-side* (Phase 2, Kotlin) concern — do **not** pre-map QIDs to ints here.
- **Determinism is a requirement:** stable sort (`key=(-sitelinks, qid)`) + sorted serialization → a
  byte-reproducible, diffable artifact. A re-run of the same version must produce identical bytes.
- **Movies only:** exclude documentary (`Q93204`) and TV-film (`Q506240`) at extract.

## The one architectural reason this pipeline exists

The server validates every move with an **O(1) in-memory set-membership check** against this graph,
loaded read-only at boot — no per-turn API call. So this pipeline's entire job is to produce a
**correct, reproducible, deterministic** bipartite artifact. Everything above is downstream of that.

## Docs — open the right one, only when you need it (context hygiene)

- **`IMPLEMENTATION_GUIDE.md`** — the "why" + the map. Primary reference for building by hand.
- **`EXPLORATION.md`** — the Wikidata source characterization (the numbers behind the decisions).
- **`docs/00–04`** — **complete reference implementations (answer keys).** These are a fallback for a
  *stuck human*, and they leak the full solution — do **not** pull them into a coaching session's context.
  Open one only on an explicit "show me the answer for stage N."
- Config contract: `src/etl/config.py` (already committed). Resolved design decisions (D1–D6):
  `docs/README.md`.
