# `etl/analysis/` — investigation code, not a pipeline stage

> **Nothing in this directory runs as part of the graph build.** It reads the same inputs the
> pipeline does (`data/graph/<version>/` and `data/raw/`) and writes nothing back into either.
> `etl/src/etl/` is the project's one fixed contract; this directory is not part of it.

## Why it lives outside `src/`

Placing analysis inside the package would make an agent read it as a build stage. The `uv_build`
backend only ships `src/`, so a sibling directory is visibly excluded from the artifact the ETL
publishes. The cost is that `ruff` and `basedpyright` scope to `src`/`tests` by default, so
`pyproject.toml` names `analysis` explicitly in both, and `pythonpath = ["."]` lets pytest import
it. That is the whole trade: three lines of config to keep the analysis linted and type-checked
while staying out of the pipeline.

**This directory never imports a private name from `etl`.** `iter_partitions` duplicates
`transform._load_rows` on purpose — an investigation is not a reason to widen the pipeline's public
surface, and five lines is the cheaper price.

## Running

```sh
cd etl
uv run python -m analysis.degree_distribution                  # → docs/investigations/001-data/
uv run python -m analysis.degree_distribution --graph-version v1 --out /tmp/summary.json
uv run pytest tests/test_analysis_degree.py
```

Requires a built artifact (`data/graph/<version>/`) and the raw partition cache (`data/raw/`).
Both are gitignored — see [../README.md](../README.md) to build them. Runtime is a couple of
seconds over 102 partitions and ~1.2M rows.

## What's here

| Script | Investigation | Produces |
|---|---|---|
| `degree_distribution.py` | [001 — Actor degree distribution](../../docs/investigations/001-actor-degree-distribution.md) | `docs/investigations/001-data/summary.json` |

## Conventions for adding another

**One module per investigation**, named for the question rather than the technique, and referenced
from the investigation document's Method section — which is the spec the script implements.

**Stamp provenance into every output.** Echo the graph version, the manifest config, and the
analysis commit. A number without the dials that produced it cannot be interpreted later, and the
dials are exactly what a sweep changes.

**Compute hypothesis verdicts in code**, against thresholds committed before measurement. A verdict
reached while reading output is a verdict that can be rationalized.

**Label post-hoc measurements as such**, in the function name, the docstring, and the output key.
A measurement designed after seeing data cannot confirm or falsify a pre-registered hypothesis, and
the output should make that impossible to forget.

**Test only where a wrong answer would be silent.** Full coverage of a one-off script is waste;
a plausible-looking wrong number that nobody questions is the actual risk. In `001` that meant
cross-partition dedupe, the genuine/cap-induced split, node classification, and decile
determinism — not the arithmetic.
