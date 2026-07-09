from dataclasses import dataclass


@dataclass(frozen=True)
class BuildConfig:
    min_sitelinks: int = 5  # notability floor (EXPLORATION: 5 → ~68k films)   [extract-time, D1]
    min_cast: int = 3  # min-cast floor (drops ~25% dead-weight films)     [transform-time]
    cast_cap: int = 15  # top-N by ACTOR sitelink count (not billing order) [transform-time]
    require_enwiki: bool = True  # English-audience recognizability anchor
    user_agent: str = "bacons-law-etl/0.1 (zach.smith33@gmail.com)"
    endpoint: str = "https://query.wikidata.org/sparql"
    year_from: int = 1900
    year_to: int = 2026
