# ETL Scale-Readiness Plan

Improvements to make the pipeline safe to run on the full 1900–2026 range, not just a
single-year smoke test. This is a plan to implement against, not code to paste.

## 1. Why

The 2015 smoke test validated correctness end-to-end. It did not exercise the operational
characteristics of a full run, which differ in kind, not just degree:

| Stage | 2015 | Full range (est.) |
|-------|------|-------------------|
| extract | 1 query, ~30s | ~126 per-year queries, ~65 min |
| transform | 10k edges, instant | ~1–2M edges, seconds |
| resolve | 8.7k QIDs, 174 batches, ~3 min | ~200–300k QIDs, ~5–6k batches, ~80 min |
| emit | small artifact | large artifact, seconds |

Two stages get long enough that a single transient failure is likely, and neither degrades
gracefully today: **resolve throws away the whole run on any non-429 error**, and **extract
aborts the entire pull on the first failed year**. The fixes below make both fault-tolerant so
an 80-minute run survives real-world network flakiness.

## 2. Resolve checkpointing — the crux

### 2.1 The problem

`resolve_labels` writes `labels.json` exactly once, after the batch loop finishes. The stage is
"resumable" only because it reads an existing `labels.json` on start — but that file doesn't
exist until a run completes. So a crash at batch 5,000 of 6,000 (a 503, a connection reset,
anything that isn't a 429) hits `resp.raise_for_status()`, and because nothing was written, the
re-run refetches from zero. At 80 minutes, this is the dominant operational risk.

### 2.2 Why a naive checkpoint breaks resume

The obvious fix — "write `labels.json` every N batches" — breaks the resume logic as written,
and this is the part that needs care. Today resolve seeds **all** missing QIDs as `None`
up front:

```python
labels = dict(existing)
labels.update({qid: None for qid in missing_qids})   # every missing QID seeded before the loop
```

Resume computes `missing_qids = all_qids - existing.keys()` — it keys on **presence**. That's
correct today because the file only exists after a complete run, so presence means "attempted."
But if you checkpoint this dict mid-loop, every QID is already present (seeded `None`), so on
resume `existing.keys()` covers everything and `missing_qids` is empty — the resume thinks it's
done when it has fetched almost nothing. `None` becomes ambiguous: "seeded but not yet fetched"
vs. "fetched, genuinely no English label."

### 2.3 The fix: seed per-batch, not up front

Move the `None` seed from before the loop to inside it, seeding only the batch being processed.
Then a checkpoint contains exactly the **attempted** QIDs (prior runs + completed batches), and
presence-based resume stays correct.

```python
existing = read_json_or_none(paths.labels_path()) or {}
missing_qids = all_qids - existing.keys()
labels: dict[str, str | None] = dict(existing)        # start from what's done; do NOT seed all

CHECKPOINT_EVERY = 50                                   # batches (~2,500 QIDs)
for i, batch in enumerate(batched(missing_qids, 50, strict=False)):
    ... fetch batch (with the existing 429 retry loop) ...
    for qid in batch:
        labels[qid] = None                              # mark THIS batch attempted
    for entity in data.entities.values():
        en = entity.labels.get("en")
        if en is not None:
            labels[entity.id] = en.value
    if (i + 1) % CHECKPOINT_EVERY == 0:
        _write_labels(labels)                           # atomic checkpoint

_write_labels(labels)                                   # final write
```

`_write_labels` is the existing sorted, atomic write factored into a helper so the checkpoint
and the final write share one path:

```python
def _write_labels(labels: dict[str, str | None]) -> None:
    write_json(paths.labels_path(), dict(sorted(labels.items())))
```

Seeding every QID of a batch to `None` before applying hits also handles the case where
`wbgetentities` omits an invalid/redirected QID from the response entirely — it's still marked
attempted, so resume won't loop on it forever.

### 2.4 Why whole-file checkpoints, not JSONL append

Appending a line per batch (JSONL) would avoid rewriting the whole file, but it reopens the
format decision emit depends on — emit reads a single sorted JSON object. Rewriting the whole
dict every 50 batches is cheap enough: ~120 checkpoints over the run, each an atomic write of a
dict growing 0→~250k entries, averaging ~125k — well within budget spread over 80 minutes, and
`write_atomic` guarantees a crash mid-write never corrupts the file. Keep the single-JSON
contract; tune `CHECKPOINT_EVERY` up (100) if the later writes feel heavy.

### 2.5 Logging

Log a line at each checkpoint so the run's durability is visible:
`log.info("checkpoint: %d/%d QIDs written", len(labels), len(all_qids))`.

## 3. Extract fault tolerance

### 3.1 The problem

`extract` raises on the first non-200 (a WDQS 504 or timeout on one heavy year), aborting the
whole pull. It's resumable via the per-year cache — a re-run skips cached years — but one bad
year shouldn't stop the other 125 from being fetched in the same pass.

### 3.2 The fix

Wrap the per-year fetch so a failure is logged and skipped rather than fatal, and report the
failed years at the end with a non-zero exit:

```python
failed: list[int] = []
for i, year in enumerate(...):
    if _cache_is_valid(cfg, year):
        ...cached...; continue
    try:
        rows = sparql.query(render_query(year, cfg), cfg)
    except httpx2.HTTPError as e:                        # 504 / timeout / connection
        log.warning("[%d/%d] %d FAILED: %s", i, total, year, e)
        failed.append(year)
        continue
    ...write payload, sleep...
# after the loop:
if failed:
    raise SystemExit(f"{len(failed)} year(s) failed: {failed}; re-run to retry (cache resumes)")
```

Optionally add a bounded retry (2–3 attempts with backoff) around the WDQS call before giving
up on a year, since WDQS 504s are frequently transient. Keep it small — the cache-resume path
already covers persistent failures.

## 4. Politeness sleep — evaluate, probably skip

Considered adding an inter-batch `time.sleep` in resolve. Sequential requests already self-pace:
each round trip is ~0.3–0.5s of inherent latency, so the stage runs at ~2–3 req/s, not a burst.
`wbgetentities` has no 60s wall and 429s are already backed off. An explicit 0.1s sleep would
add ~10 minutes over 6,000 batches for negligible politeness gain. **Recommendation: skip it**;
revisit only if a run actually draws 429s.

## 5. Testing

- **Checkpoint resumability (resolve):** with a stubbed fetch, run part-way, write a checkpoint,
  then re-run and assert it fetches only the un-attempted QIDs (not the null-but-attempted ones).
  This is the regression guard for the §2.2 trap.
- **Checkpoint atomicity:** assert `labels.json` after a mid-run checkpoint has attempted-only
  keys and is valid JSON.
- **Extract skip-on-failure:** stub one year to raise `httpx2.HTTPError`; assert the other years
  still write, the failed year is logged, and the stage exits non-zero with the year listed.

## 6. Operational runbook (first full build)

Run stages separately, not `build` in one shot — the disk seam exists so a failure in one stage
doesn't cost the others.

1. **Mid-size trial first** — run all four stages for `--year-from 2010 --year-to 2020` (11
   years, ~10x the smoke test). Confirms scaling behavior — extract time/year, transform memory,
   resolve batch count — at 10x before committing to 126x.
2. **extract** the full range; re-run until every year reports cached (resumable; §3 makes one
   bad year non-fatal).
3. **transform** once; sanity-check edge/QID counts.
4. **resolve**; the long pole, now checkpointed — a crash resumes near where it stopped.
5. **emit** → `data/graph/v1/`; verify the manifest counts and that entities carry real names.

## 7. Checklist & sequencing

1. **resolve:** factor `_write_labels`; move the `None` seed into the loop (per-batch); add
   `CHECKPOINT_EVERY` writes + checkpoint log line. (§2 — required for a full run.)
2. **resolve test:** checkpoint-resume regression test. (§5)
3. **extract:** skip-on-failure + failed-year report; optional bounded retry. (§3 — de-risks the
   ~65-min pull.)
4. **extract test:** skip-on-failure test. (§5)
5. Skip the politeness sleep. (§4)
6. Mid-size trial, then staged full run. (§6)

Do 1–2 first — they close the dominant risk (an 80-minute resolve losing everything on a blip).
3–4 are the next-most valuable. Then trial at 2010–2020 before the full range.
