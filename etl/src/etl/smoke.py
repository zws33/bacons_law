"""Manual smoke script: run the extract query for a single year and cache it.

Run it as a module (src-layout — running by file path breaks `import etl`):

    uv run python -m etl.smoke          # defaults to year 1925
    uv run python -m etl.smoke 1994     # any year
"""

import json
import logging
import sys

from etl.config import BuildConfig
from etl.extract import render_query
from etl.paths import RAW_DIR
from etl.sparql import SparqlError, query

log = logging.getLogger("etl.smoke")


def run(year: int) -> None:
    config = BuildConfig()
    log.info("querying: year=%d min_sitelinks=%d", year, config.min_sitelinks)

    try:
        rows = query(render_query(year, config), config)
    except SparqlError:
        log.exception("WDQS query failed for year %d", year)
        raise SystemExit(1) from None

    log.info("received %d rows", len(rows))
    for r in rows[:3]:
        log.info("sample: %s", r)

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"smoke-{year}.json"
    _ = path.write_text(json.dumps(rows))
    log.info("wrote %d rows to %s", len(rows), path)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 1925
    run(year)
