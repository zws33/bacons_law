import logging
import time
from datetime import UTC, datetime
from typing import NamedTuple

from pydantic import ValidationError

from etl import sparql
from etl.config import BuildConfig
from etl.io import read_json_or_none, write_atomic
from etl.models import CacheHeader, CachePayload
from etl.paths import RAW_DIR, raw_path

FILM = "Q11424"
DOCUMENTARY = "Q93204"
TV_FILM = "Q506240"

# Bump whenever render_query's SHAPE changes (new column, changed pattern) — anything a
# cached partition's rows were flattened from. It is part of the cache key, so a bump
# invalidates every partition. Config values baked into the query (min_sitelinks) are
# compared separately and don't need a bump.
QUERY_VERSION = 2

logger = logging.getLogger(__name__)


def render_query(year: int, config: BuildConfig) -> str:
    return f"""
PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX schema: <http://schema.org/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

SELECT ?film ?filmLabel ?articleName ?filmSitelinks ?actor ?actorLabel ?actorSitelinks WHERE {{
  ?film wdt:P31 wd:{FILM} ;               # instance of: film
        wikibase:sitelinks ?filmSitelinks ;
        wdt:P577 ?date ;                   # publication date → partition key
        wdt:P161 ?actor .                  # cast member (the edge)
  ?actor wikibase:sitelinks ?actorSitelinks .

  FILTER(?filmSitelinks >= {config.min_sitelinks})
  FILTER(YEAR(?date) = {year})               # ← the partition; substitute per run
  FILTER NOT EXISTS {{ ?film wdt:P31 wd:{DOCUMENTARY} }}  # exclude documentary
  FILTER NOT EXISTS {{ ?film wdt:P31 wd:{TV_FILM} }}  # exclude TV film

  # enwiki anchor (recognizability): require an English Wikipedia article
  ?article schema:about ?film ; schema:isPartOf <https://en.wikipedia.org/> .

  OPTIONAL {{ ?film  rdfs:label ?filmLabel  . FILTER(LANG(?filmLabel)  = "en") }}
  OPTIONAL {{ ?actor rdfs:label ?actorLabel . FILTER(LANG(?actorLabel) = "en") }}

  # Film display-name fallback. A prominent item can have an enwiki ARTICLE and still have
  # no English LABEL (Q20856802 / "La La Land": 73 sitelinks, 41 labels, no en). The anchor
  # above already binds ?article, so its title costs no extra join. OPTIONAL on purpose —
  # a required pattern here would DROP any film whose article lacks schema:name rather than
  # degrade its label, trading a cosmetic gap for a missing node.
  OPTIONAL {{ ?article schema:name ?articleName }}
}}
"""


def _cache_is_valid(cfg: BuildConfig, year: int) -> bool:
    path = raw_path(year)
    if not path.exists():
        return False
    try:
        data = CacheHeader.model_validate(read_json_or_none(path))
    except ValidationError:
        return False

    return (
        data.min_sitelinks == cfg.min_sitelinks
        and data.endpoint == cfg.endpoint
        and data.query_version == QUERY_VERSION
    )


class ExtractStats(NamedTuple):
    fetched: int
    cached: int


def extract(cfg: BuildConfig) -> ExtractStats:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    writes_count = 0
    cached_count = 0

    total = cfg.year_to - cfg.year_from + 1
    failed_years: list[int] = []
    for i, year in enumerate(range(cfg.year_from, cfg.year_to + 1), start=1):
        path = raw_path(year)
        if _cache_is_valid(cfg, year):
            logger.info("[%d/%d] %d cached", i, total, year)
            cached_count += 1
            continue

        logger.info("[%d/%d] fetching %d...", i, total, year)
        start = time.perf_counter()
        try:
            rows = sparql.query(render_query(year, cfg), cfg)
        except sparql.SparqlError as e:
            logger.warning("[%d/%d] %d failed: %s", i, total, year, e)
            failed_years.append(year)
            continue

        logger.info(
            "[%d/%d] %d: fetched %d rows in %.1f s",
            i,
            total,
            year,
            len(rows),
            time.perf_counter() - start,
        )

        payload = CachePayload(
            year=year,
            fetched_at=datetime.now(UTC).isoformat(),
            endpoint=cfg.endpoint,
            min_sitelinks=cfg.min_sitelinks,
            query_version=QUERY_VERSION,
            row_count=len(rows),
            rows=rows,
        )
        write_atomic(path, payload.model_dump_json())
        writes_count += 1
        time.sleep(1)  # be a good citizen; don't burst WDQS
    if failed_years:
        raise SystemExit(f"Failed to fetch {len(failed_years)} years: {failed_years}. ")
    return ExtractStats(fetched=writes_count, cached=cached_count)
