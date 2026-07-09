import json
import time

from etl.config import BuildConfig
from etl.paths import RAW_DIR, raw_path
from etl.sparql import query as wd_query

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


def extract(cfg: BuildConfig) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for year in range(cfg.year_from, cfg.year_to + 1):
        path = raw_path(year)
        if path.exists():
            continue
        rows = wd_query(render_query(year, cfg), cfg)  # raises on timeout → let it, then rerun
        _ = path.write_text(json.dumps(rows))
        time.sleep(1)  # be a good citizen; don't burst
