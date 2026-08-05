# Python/FastAPI showcase — archived docs

This folder preserves the documentation for the **Python/FastAPI multi-device showcase** of Bacon's
Law. That implementation was a learning exercise — hands-on FastAPI, async, WebSockets, Redis, and a
real comparison of tech-stack tradeoffs (the latter distilled into [`../CASE_STUDY.md`](../CASE_STUDY.md)).
It is **complete and not maintained further**.

The code lives on the **`fullstack-py-ts-rewrite`** branch, tagged **`python-fastapi-showcase`**
(`git checkout python-fastapi-showcase`). It is not present in the trunk's tree.

These docs are kept verbatim for historical context. They are **superseded by the trunk's direction**
— a Kotlin/Ktor server validating moves against a precomputed, in-process bipartite graph built by a
Python ETL from CC0 Wikidata data. See the live decision log [`../DECISIONS.md`](../DECISIONS.md) for
the current plan, and `../CASE_STUDY.md` for the reasoning that motivated the pivot (notably:
validation belongs offline + in-process, not as a per-turn external API call).

| Archived (Python) | Current (trunk) |
|---|---|
| [`PYTHON_TS_REWRITE_PLAN.md`](PYTHON_TS_REWRITE_PLAN.md) — initiative source of truth | *(no roadmap document at present — pending regeneration)* |
| [`PHASE_0_PLAN.md`](PHASE_0_PLAN.md) … [`PHASE_5_PLAN.md`](PHASE_5_PLAN.md) — per-phase plans | *(superseded)* |
| [`DECISIONS.md`](DECISIONS.md) — ADRs 008–009 (Python-framed) | [`../DECISIONS.md`](../DECISIONS.md) — canonical log |
| Engine spec | *(the trunk's prose specs were retired; `kotlin/core/.../GameEngine.kt` is the spec of record)* |

> **Note on internal links.** These docs were authored when they lived in `docs/`. Some relative
> links inside the phase plans (e.g. `GAME_SPEC_V2.md`, `kotlin/...`) reflect that original layout
> and will not resolve from `docs/python/`. `GAME_SPEC_V2.md` has since been deleted from the trunk
> altogether — where these plans cite it as the authoritative engine contract, the trunk's equivalent
> is now `kotlin/core/.../GameEngine.kt` and its tests. The live decision log is
> [`../DECISIONS.md`](../DECISIONS.md). The text is preserved as a faithful snapshot rather than
> rewritten.
