# ETL Logging — Implementation Plan

Progress feedback for the ETL CLI. This is a plan to implement against, not code to paste.

## 1. Why

Running `extract` for a single year printed nothing for ~30s, then one line. There was no
way to tell a working command from a hung one. Root cause: `extract` only logs *after* each
network call (`extract.py`, the `print(f"fetched {year}...")` line), so a single blocking
`sparql.query` leaves the terminal silent until it returns. A compounding factor is buffering
— stdout is block-buffered when it isn't a TTY (piped output, some `uv run` cases), so even
existing prints can sit unseen until the process exits.

The forcing function is the **resolve** stage that comes next: it will run thousands of
`wbgetentities` requests over ~80 minutes. A silent 30-second command is annoying; a silent
80-minute one is unusable. Standing up one logging pattern now means every stage — including
resolve — speaks the same way for free, instead of hand-rolling `print` twice.

## 2. Principles

1. **Progress on stderr, results on stdout.** Per-item chatter ("fetching 2015…") is progress
   → stderr. The final one-line summary ("extract: 1 fetched, 0 cached") is the result →
   stdout. This keeps stdout clean the day anyone pipes the CLI.
2. **Emit a line _before_ each blocking call, not just after.** A "starting" line is what
   distinguishes "working" from "hung". The post-call line reports the outcome.
3. **Per-item log lines, not a progress bar.** No `tqdm` / `rich`. A spinner adds a
   dependency, breaks when output is redirected to a file, and needs a TTY. The work is chunky
   (~30s network calls; batches of 50 QIDs), so one line per unit — with elapsed time — is the
   right granularity *and* it survives `... > run.log` and `tail -f`.
4. **Let the logger do the formatting.** `log.info("%d: %d rows", year, n)`, not
   `log.info(f"{year}: {n} rows")`. Deferred formatting is the logging idiom and keeps ruff
   quiet.
5. **`logging`, not `print(file=sys.stderr)`.** `StreamHandler` flushes each record (buffering
   problem gone), gives verbosity levels for free, and is testable via pytest's `caplog`.

## 3. Design

### 3.1 Configure once, in `main()`

`logging.basicConfig` is called exactly once, early in `__main__.main()` right after argument
parsing, before any stage runs:

```python
import logging, sys

level = logging.INFO
if args.quiet:
    level = logging.WARNING
if args.verbose:
    level = logging.DEBUG
logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr)
```

- `format="%(message)s"` keeps output clean (no `INFO:etl.extract:` prefix noise). If the
  long resolve run wants wall-clock stamps, switching to `"%(asctime)s  %(message)s"` is a
  one-line change — worth it for resolve, optional for the fast stages.
- `stream=sys.stderr` is the stderr/stdout split from principle 1.

### 3.2 A logger per module

Each stage module gets a module-level logger and uses it instead of `print` for progress:

```python
import logging
log = logging.getLogger(__name__)
```

`__name__` yields `etl.extract`, `etl.resolve_labels`, etc. — so verbosity can later be tuned
per stage if ever needed, at no cost now.

### 3.3 Verbosity flags (`-v` / `-q`)

Two global flags: `--verbose/-v` → DEBUG, `--quiet/-q` → WARNING, default INFO.

**argparse gotcha:** a flag on the *top-level* parser must appear before the subcommand
(`etl -v extract`), which is awkward. To allow the natural `etl extract -v`, put the flags on
a parent parser and hand it to every subparser via `parents=`:

```python
common = argparse.ArgumentParser(add_help=False)
common.add_argument("-v", "--verbose", action="store_true", help="debug-level logging")
common.add_argument("-q", "--quiet", action="store_true", help="warnings and errors only")
# then: sub.add_parser("extract", parents=[common], help=...)  for each subcommand
```

This is separate from `_add_config_args` (gameplay dials) on purpose — logging verbosity isn't
a build knob and shouldn't ride in the same helper.

## 4. Per-stage plan

### 4.1 `extract` — the stage that needed this

Add a counter, elapsed timing, a **pre-call** line, and a "cached" line so skipped years still
show progress:

```python
log = logging.getLogger(__name__)
total = cfg.year_to - cfg.year_from + 1
for i, year in enumerate(range(cfg.year_from, cfg.year_to + 1), start=1):
    if _cache_is_valid(cfg, year):
        log.info("[%d/%d] %d cached", i, total, year)
        cached_count += 1
        continue
    log.info("[%d/%d] fetching %d…", i, total, year)          # BEFORE the blocking call
    t0 = time.perf_counter()
    rows = sparql.query(render_query(year, cfg), cfg)
    log.info("[%d/%d] %d: %d rows in %.1fs",
             i, total, year, len(rows), time.perf_counter() - t0)
    # ... write payload, sleep ...
```

Replaces the existing bare `print(f"fetched {year}: {len(rows)} rows")`.

### 4.2 `transform` / `emit` — pure and fast, lighter touch

Not the pain point, but they should speak the same language for consistency:

- `transform`: `log.info("loading %d partitions", n)` after the glob; the rich stats line
  (edges · movies · actors · distinct QIDs) stays as the stdout *result*.
- `emit`: `log.info("writing graph/%s", version)` before the write.

Optional — add only if it reads well; don't manufacture noise.

### 4.3 `resolve` — the reason we're doing this now (future)

When built, resolve inherits the pattern and adds batch-level progress and an ETA hint:

```python
log.info("labels: %d distinct QIDs, %d cached, fetching %d", total, cached, len(missing))
# per batch:
log.info("[batch %d/%d] +%d labels (%d/%d done)", b, n_batches, got, done, len(missing))
```

For an 80-minute run this is what makes it monitorable via `tail -f`.

## 5. stdout vs stderr — the split, concretely

| Output | Stream | Mechanism |
|--------|--------|-----------|
| Per-year / per-batch progress | stderr | `log.info(...)` |
| Elapsed timings | stderr | `log.info(...)` |
| Final stage summary (`extract: 1 fetched, 0 cached`; the transform stats line) | stdout | `print(...)` in `__main__._run_*` |
| Errors / `SystemExit` messages | stderr | logging / `raise SystemExit` |

Keep the `_run_*` summary `print`s as-is — they are results, not progress.

## 6. Non-goals

- No `tqdm` / `rich` / progress bars (principle 3).
- No log files or JSON/structured logging — stderr only; the user redirects if they want a
  file (`etl build ... 2> build.log`).
- No logging config framework — `basicConfig` is sufficient for a single-process offline CLI.

## 7. Testing

Stage unit tests call the stage functions directly (they never hit `main()`, so `basicConfig`
isn't involved). Assert on log output with pytest's `caplog` fixture:

```python
def test_extract_logs_progress(caplog):
    with caplog.at_level(logging.INFO):
        ...
    assert any("fetching" in r.message for r in caplog.records)
```

Progress logging is cheap to assert and worth one test per stage that it announces work before
doing it (guards against silently regressing the pre-call line).

## 8. Implementation checklist

1. `__main__.py`: `common` parent parser with `-v/-q`; `parents=[common]` on every subparser;
   `logging.basicConfig(...)` early in `main()` from the parsed flags.
2. `extract.py`: module logger; counter + `perf_counter` timing; **pre-call** `fetching` line;
   `cached` line; drop the old `print`.
3. `transform.py` / `emit.py`: module logger; one or two `log.info` lines; keep the stdout
   result summaries.
4. (later) `resolve_labels.py`: same logger pattern + batch progress + counts.
5. One `caplog` test per stage asserting it announces work.

Do 1–2 first (that is the actual fix), confirm a re-run of the 2015 smoke test now narrates
itself, then carry the pattern into resolve when we build it.
