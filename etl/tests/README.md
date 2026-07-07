# The guided test harness

A test suite you run **while** you build, as a safety net and a guide. It's written against the
answer-key docs in [`../docs/`](../docs/), so making it green means your code matches the intended
design. It's aimed at catching the Python "gotchas" and the pipeline-specific traps before they bite.

## How it behaves (this is the important part)

You're building from empty files, so the harness is designed to **degrade gracefully**:

| Situation | What the harness does |
|-----------|-----------------------|
| A module/function you haven't written yet | **SKIP** with "not built yet" — never an error dump |
| A Python **syntax error** in your file | **FAIL** with the file + line number, no traceback wall |
| A missing package you own (e.g. models before it exists) | **SKIP** with what to build first |
| A real **logic mistake** | **FAIL** with a message that names the likely fix |

So a normal run early on is mostly *skips* — that's expected, not failure. Skips turn into passes as you
build.

## Running it

```bash
uv run pytest                      # everything; prints the progress dashboard
uv run pytest tests/test_02_transform.py   # just one stage while you work on it
uv run pytest -q -k tie_break      # a single test by name fragment
uv run pytest --run-live           # ALSO run the one real-network test (Stage 1 smoke)
```

After every run you get a per-stage map:

```
======================= Bacon's Law ETL — build progress =======================
  ✅  Stage 0 · shared types  (config / models / paths) — 5 passing
  🚧  Stage 1 · extract        (sparql + fetch loop) — 4 passing, 1 to go
  ⬜  Stage 2 · transform      (filter / cap / fold) — not started
  ...
  ✅ done    🚧 in progress    ⬜ not started    ❌ failing
```

Build in order — Stage 0 → 4 — and drive each stage's block to ✅ before moving on.

## What each file checks

| File | Stage | Key things it guards |
|------|-------|----------------------|
| `test_00_shared.py` | 0 | config defaults + frozen; models construct; **`Film.cast` isn't a shared mutable default**; `paths.ROOT` is the `etl/` dir |
| `test_01_extract.py` | 1 | URI→QID stripping; **sitelinks parsed to `int`**; query fully templated from config; **cache invalidates on param change (D1)**; (`--run-live`) real smoke |
| `test_02_transform.py` | 2 | cap keeps top-N; **ties break by QID (determinism)**; min-cast floor boundary; dedup across partitions; deterministic edge order |
| `test_03_emit.py` | 3 | adjacency **symmetry**; entities typed/deduped; **lists serialized sorted**; QID keys (not ints); manifest config+counts; reproducible re-run |
| `test_04_pipeline.py` | 4 | CLI flag→config mapping; **full extract→transform→emit** into a temp tree (no network); cache reuse on re-run |

`conftest.py` provides the dashboard + `--run-live` flag. `_harness.py` holds the `require()` lazy-loader
and the data factories. Neither imports your code at load time.

## Assumptions (so a failure isn't a false alarm)

The tests assume the **public API from the answer keys**: the function names and signatures in
`../docs/`. Examples: `sparql.query(text, config)`, `extract.render_query(year, config)`,
`transform.films_to_edges(films, config)`, `emit.emit(edges, config, version)`. If you deliberately
choose different names, update the matching test — the harness is yours to edit. The HTTP-client test
also assumes you `import httpx2` (as `httpx` or as `httpx2`); patch accordingly if you use a different
client.

## If everything in a stage is skipping and you think it shouldn't

Run that one file with `-ra` to see the skip reasons:

```bash
uv run pytest tests/test_02_transform.py -ra
```

The reason line tells you exactly which module/attr it's waiting on.
