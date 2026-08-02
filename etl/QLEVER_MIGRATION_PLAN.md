# ETL — QLever Migration Plan

Move the extract off WDQS onto QLever, and restore labels to the main query.
This is a plan to implement against, not code to paste.

## 1. The finding

`6af796e` ("Phase 1 — offline Wikidata graph build pipeline") completed the pipeline with labels
selected inline:

```sparql
SELECT ?film ?filmLabel ?filmSitelinks ?actor ?actorLabel ?actorSitelinks WHERE {
    ...
    SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

`SERVICE wikibase:label` blew the WDQS 60-second wall on a *single year*. `5736262` removed it and
built the `resolve` stage — `wbgetentities` batching, `labels.json`, presence-based resume — to
compensate, and `889b718` added checkpointing so that stage could survive an 80-minute run.

That was the right response to the constraint, and it wasn't enough. Without labels a single year
completed in ~30s, but the full 1900–2026 pull still hit timeouts. **WDQS could not serve this
volume at any decomposition** — not with labels inline, not with labels split out, not partitioned
by year. That is the failure that opened this investigation.

**The 60-second wall is a WDQS operational policy, not a property of SPARQL or of Wikidata.** QLever
answers the whole range *with* labels in 4.3 seconds. It is not that the workaround was wrong; it is
that the constraint forcing it is gone, and so is the larger constraint the workaround never
addressed.

The target shape is therefore `6af796e` — the last version where labels came from the query. This is
a restoration, not a redesign.

### 1.1 What the spike measured

| Check | Result |
|-------|--------|
| 2015 edge sets, QLever vs WDQS | **identical** — 12,895 pairs, 1,335 films, 9,814 actors |
| 2015 sitelink counts | 88 of 11,149 entities differ, deltas bidirectional |
| Full range, one query | 1,228,492 rows, 6,702 ms |
| Same query with `OPTIONAL` label joins | 1,228,492 rows — **identical** — 4,302 ms |
| Films or actors with >1 English label | **none** |
| Query without `PREFIX` declarations | **rejected** — QLever has no default prefixes |
| Implied distinct films | ~68k — matches `EXPLORATION.md`'s `min_sitelinks=5` characterization |

Read the timings as "labels cost nothing detectable," not as labels being faster than no labels — the
labelled query ran second and QLever caches shared subtrees.

The index also drifts: the same query returned 1,228,396 rows on Jul 31 and 1,228,492 on Aug 2,
~0.008%/day. That is normal Wikidata churn in a live index. It is an argument for one query rather
than two — a separate label pull hours later can disagree about which entities exist.

## 2. Scope

**Restore `6af796e`'s shape. Keep everything that landed after it.** Three later changes are
independent of the label question and stay:

- `7df0ae4` — graph artifact written under `data/` so it's gitignored
- `889b718` — fault-tolerant extract (`failed_years`, skip-and-report)
- the progress logging and `TransformStats` bundled into `5736262`

So this is **not** `git revert 5736262` — that would take the logging with it and conflict with
everything after. Use `git diff 6af796e HEAD -- etl/src/etl/` as the reference for what the label
removal cost, and restore selectively.

**Year partitioning stays.** Each year is ~23k rows, well within `response.json()`. Collapsing to one
query is §7, a documented follow-on.

| File | Change |
|------|--------|
| `config.py` | `endpoint` → `https://qlever.dev/api/wikidata` |
| `extract.py` | `render_query` only: `PREFIX` block; `SERVICE wikibase:label` → two `OPTIONAL rdfs:label` blocks |
| `sparql.py` | restore label extraction in `_flatten`, with `.get()` (§4) |
| `models.py` | restore `film_label`/`actor_label` on `WikidataRow`; `movie_label`/`actor_label` on `Edge` |
| `transform.py` | restore label passthrough; `_load_rows` → generator (§5) |
| `emit.py` | restore `_build_entities(edges)`; drop `_load_labels` |
| `paths.py` | drop `labels_path()` |
| `__main__.py` | drop the `resolve` subcommand, `_run_resolve_labels`, and the `build` step |
| `resolve_labels.py` | **delete** |

There is no `labels.json`. At `6af796e`, `Edge` carried `movie_label` and `actor_label` and
`_build_entities(edges)` read them directly. An earlier draft of this plan proposed a `labels.json`
produced by `transform`; that was designing around a problem this shape doesn't have.

## 3. `render_query` — two changes

**The `PREFIX` block is mandatory** — `wd:`, `wdt:`, `wikibase:`, `schema:`, `rdfs:`. WDQS injects
them silently; QLever rejects the query without them (measured). Keeping them explicit is also what
makes the WDQS fallback in §6 a config change rather than a rewrite.

**Replace the `SERVICE` line** with two `OPTIONAL` joins — `SERVICE wikibase:label` is a Wikibase
extension QLever doesn't implement:

```sparql
OPTIONAL { ?film  rdfs:label ?filmLabel  . FILTER(LANG(?filmLabel)  = "en") }
OPTIONAL { ?actor rdfs:label ?actorLabel . FILTER(LANG(?actorLabel) = "en") }
```

`OPTIONAL`, not plain patterns — an entity with no English label must still produce its edge.
Verified to add zero rows at full scale, and no entity on either side carries two English labels, so
there is no fan-out to defend against.

Everything else in `render_query` — the year filter, the sitelinks floor, the enwiki block, the
documentary and TV-film exclusions — is unchanged.

## 4. The one behavioral difference

`SERVICE wikibase:label` **always binds**: it falls back to the QID when no label exists. `OPTIONAL`
**leaves the variable unbound**, and in `application/sparql-results+json` an unbound variable is
*omitted from the binding object entirely* — not present-and-null.

So `6af796e`'s `_flatten` line does not port as-is:

```python
"film_label": b["filmLabel"]["value"],   # KeyError on any unlabelled entity
```

`_flatten` already catches `KeyError` and raises `SparqlError`, so this fails loudly rather than
corrupting anything — but it fails the whole pull on the first unlabelled entity, with an error
about response shape rather than a missing optional.

**Apply the QID fallback in `_flatten`.** That restores the guarantee `6af796e` relied on
(`film_label: str`, never `None`), so `Edge`, `transform`, and `emit` need no defensive handling.
The cost is that a display decision now lives in the extract stage instead of at WDQS — worth one
comment saying so.

This will essentially always be an **actor**. Films must clear `min_sitelinks >= 5` and have an
English Wikipedia article, which all but guarantees an English label; actors have neither constraint.
Put the fixture there.

## 5. `transform._load_rows` should become a generator

Independent of everything above, and easy to miss in a restoration. It accumulates every row:

```python
rows: list[WikidataRow] = []
...
rows.extend(data.rows)
```

At 1.23M rows that is ~440MB of dicts, plus ~120MB of label strings which — unlike QIDs — are not
shared across rows. Yielding per partition keeps resident memory to the `films` dict.
`_build_edge_list` iterates once, so it consumes an iterator unchanged.

It will complete without this on a machine with room. It is a should-fix, not a blocker.

## 6. Risk, and the ADR

QLever is a third-party, best-effort service with no SLA; WDQS is the official Wikimedia endpoint.
You are trading slow-and-rate-limited for fast-and-unguaranteed.

Be honest about how much of a dependency this is. **WDQS is not a fallback** — §1 is the whole point:
it could not serve this volume with labels, without labels, or partitioned. Falling back to it means
a partial build of recent years, not a full one. The query staying portable is worth something for
spot-checking and for a reduced range, but it does not get you an artifact.

1. **The dump pipeline is the real floor.** More work, depends on nothing but the dumps, and it is
   the only alternative that produces a complete graph. Keep the design note; you now know you don't
   need it *today*.
2. **Back up `data/raw/` off this laptop** the moment the full pull lands. This matters more than it
   would if WDQS were a viable fallback: `data/` is gitignored, and a raw cache you already hold is
   the difference between a QLever outage being an inconvenience and being a rebuild from a 150GB
   dump. The artifact under `data/graph/<version>/` is worth backing up for the same reason.
3. **The query stays portable.** Explicit prefixes mean it runs on WDQS apart from the label joins.
   Useful for verification against the official endpoint, not for production builds.

Worth an ADR — it changes the data-acquisition path, which `AGENTS.md` states as load-bearing fact.
**ADR 014** in `docs/DECISIONS.md`.

## 7. Follow-on: collapse to one query

Out of scope, recorded so it isn't lost. One full-range query returns 1.23M rows in ~7s versus ~127
queries at a couple of seconds each — a few minutes' saving, which is why it isn't urgent.

It would require dropping the year loop, adding `?date` to the SELECT and moving the year filter to
`transform` (making `year_from`/`year_to` free to retune — the actual prize), and switching
`sparql.py` to streaming TSV, since 1.23M rows of `sparql-results+json` is >1GB materialized. That
last item is most of the work and introduces silent truncation as a failure mode that year
partitioning currently makes impossible.

Contained to `extract.py` and `sparql.py`. Do it when the loop annoys you.

## 8. Tests

- `test_sparql.py` — a fixture row with a **missing** label binding. This is §4, the one genuinely
  new failure mode. `data/spike/films-2015.tsv` is a real QLever response worth keeping as a fixture;
  you have the WDQS answer to assert against.
- `test_transform.py` / `test_emit.py` — `git diff 6af796e HEAD -- etl/tests/` shows what the label
  removal changed; most of it restores.
- `test_cli.py` / `test_pipeline.py` — the `resolve` subcommand is gone.
- Delete `test_resolve_labels.py`.

## 9. Docs

- **`etl/AGENTS.md`** — the endpoint, and qualify the ~60s wall as WDQS-specific rather than inherent
  to SPARQL. The three-stage pipeline description is correct again once `resolve` is gone. Its "Docs"
  section still points at `docs/00–04` and `docs/README.md`, which no longer exist — that block needs
  rewriting or removing.
- **`IMPLEMENTATION_GUIDE.md`** — its "labels carried on the edges" line (~249) was written for the
  `6af796e` shape and is accurate again after this migration. Check the rest for references to the
  deleted `docs/` tree.
- **`.opencode/prompts/tutor.md`** — instructs against opening `etl/docs/00-*.md … 04-*.md` as answer
  keys. Those files are gone; the instruction is now dead.
- **`docs/DECISIONS.md`** — ADR 014, per §6. Frame it as "accept a third-party dependency because the
  official endpoint cannot serve this workload," not "swap endpoints" — §1 and §6 are the substance.
- **`EXPLORATION.md`** — no change; its characterization held and the spike corroborated it.
- **Already deleted:** `SCALE_READINESS_PLAN.md` (§2 protected a stage that no longer exists; §3
  shipped in `889b718`), `LOGGING_PLAN.md` (shipped in `5736262`), and the whole `etl/docs/` tree of
  staged reference implementations. Git history holds them.

## 10. Sequencing

1. **`config.py` endpoint + `render_query` `PREFIX` block**, no labels yet. Run `extract` for 2015
   and diff against `data/spike/films-2015.tsv`. Verifies the endpoint switch in isolation.
2. **Labels:** the `OPTIONAL` joins, `_flatten` with `.get()` + QID fallback, `models.py` fields.
   Re-run 2015; confirm labels arrive and an unlabelled actor doesn't fail the pull.
3. **Restore the passthrough:** `transform.py`, `emit.py`, `paths.py`.
4. **Delete `resolve_labels.py`**, update `__main__.py`, fix the tests.
5. **`_load_rows` generator** (§5).
6. **Full build.** Diff the 2015 slice of the new artifact against the current `data/graph/v1/` — a
   known-good comparison built from independently verified WDQS data.
7. **Docs and ADR** (§9), then delete `data/spike/`.

Step 1 changes one thing and is independently verifiable; don't bundle it with step 2. Step 6 is the
acceptance test.
