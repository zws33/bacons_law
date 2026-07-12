import json
import time
from datetime import UTC, datetime
from pathlib import Path

from etl import sparql
from etl.config import BuildConfig
from etl.paths import RAW_DIR, raw_path

FILM = "Q11424"
DOCUMENTARY = "Q93204"
TV_FILM = "Q506240"


def render_query(year: int, config: BuildConfig) -> str:
    """Fully templated from config (D2): min_sitelinks, the enwiki block, and the year."""
    enwiki_block = (
        "?article schema:about ?film ; schema:isPartOf <https://en.wikipedia.org/> ."
        if config.require_enwiki
        else ""
    )
    return f"""
    SELECT ?film ?filmLabel ?filmSitelinks ?actor ?actorLabel ?actorSitelinks WHERE {{
        ?film wdt:P31 wd:{FILM} ;
                wikibase:sitelinks ?filmSitelinks ;
                wdt:P577 ?date ;
                wdt:P161 ?actor .
        ?actor wikibase:sitelinks ?actorSitelinks .

        FILTER(?filmSitelinks >= {config.min_sitelinks})
        FILTER(YEAR(?date) = {year})
        FILTER NOT EXISTS {{ ?film wdt:P31 wd:{DOCUMENTARY} }}
        FILTER NOT EXISTS {{ ?film wdt:P31 wd:{TV_FILM} }}
        {enwiki_block}
        SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}"""


def _cache_is_valid(cfg: BuildConfig, year: int) -> bool:
    path = raw_path(year)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return False  # corrupt/half-written file → re-fetch
    if not isinstance(data, dict):
        return False  # stale bare-list format from an older extract → re-fetch
    return (
        data.get("require_enwiki") == cfg.require_enwiki
        and data.get("min_sitelinks") == cfg.min_sitelinks
    )


def extract(cfg: BuildConfig) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for year in range(cfg.year_from, cfg.year_to + 1):
        path = raw_path(year)
        if _cache_is_valid(cfg, year):
            print(f"skip {year} (cached)")
            continue

        rows = sparql.query(render_query(year, cfg), cfg)  # raises on timeout → let it, then rerun
        payload = {
            "year": year,
            "fetched_at": datetime.now(UTC).isoformat(),
            "endpoint": cfg.endpoint,
            "min_sitelinks": cfg.min_sitelinks,
            "require_enwiki": cfg.require_enwiki,
            "row_count": len(rows),
            "rows": rows,
        }
        _write_atomic(path, payload)
        print(f"fetched {year}: {len(rows)} rows")
        time.sleep(1)  # be a good citizen; don't burst WDQS


def _write_atomic(path: Path, payload: dict) -> None:
    """Write to a temp sibling then rename; an interrupted run never leaves a half-written cache."""
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload))
    tmp.replace(path)
