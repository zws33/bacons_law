from dataclasses import dataclass


@dataclass(frozen=True)
class BuildConfig:
    min_sitelinks: int = 5  # notability floor (EXPLORATION: 5 → ~68k films)
    min_cast: int = 3  # min-cast floor (drops ~25% dead-weight films)
    cast_cap: int = 15  # top-N by ACTOR sitelink count (not billing order)
    require_enwiki: bool = True  # English-audience recognizability anchor
    user_agent: str = "bacons-law-etl/0.1 (zach.smith33@gmail.com)"
    endpoint: str = "https://query.wikidata.org/sparql"
