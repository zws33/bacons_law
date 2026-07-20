import time
from datetime import UTC, datetime

from pydantic import ValidationError

from etl import sparql
from etl.config import BuildConfig
from etl.io import read_json_or_none, write_atomic
from etl.models import CachePayload
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
        data = CachePayload.model_validate(read_json_or_none(path))
    except ValidationError:
        return False

    return (
        data.require_enwiki == cfg.require_enwiki
        and data.min_sitelinks == cfg.min_sitelinks
        and data.endpoint == cfg.endpoint
    )


def extract(cfg: BuildConfig) -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    writes_count = 0
    for year in range(cfg.year_from, cfg.year_to + 1):
        path = raw_path(year)
        if _cache_is_valid(cfg, year):
            print(f"skip {year} (cached)")
            continue

        rows = sparql.query(render_query(year, cfg), cfg)
        payload = CachePayload(
            year=year,
            fetched_at=datetime.now(UTC).isoformat(),
            endpoint=cfg.endpoint,
            min_sitelinks=cfg.min_sitelinks,
            require_enwiki=cfg.require_enwiki,
            row_count=len(rows),
            rows=rows,
        )
        write_atomic(path, payload.model_dump_json())
        print(f"fetched {year}: {len(rows)} rows")
        writes_count += 1
        time.sleep(1)  # be a good citizen; don't burst WDQS
    return writes_count
