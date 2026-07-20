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

    def __post_init__(self) -> None:
        # Fail at construction, not with an empty artifact three stages later. An inverted
        # year range or a zero cap yields zero edges, which is indistinguishable from a
        # successful build of nothing unless we reject it here.
        if self.year_from > self.year_to:
            raise ValueError(f"year_from {self.year_from} > year_to {self.year_to}")
        if self.cast_cap < 1:
            raise ValueError(f"cast_cap must be >= 1, got {self.cast_cap}")
        if self.min_cast < 1:
            raise ValueError(f"min_cast must be >= 1, got {self.min_cast}")
        if self.min_sitelinks < 0:
            raise ValueError(f"min_sitelinks must be >= 0, got {self.min_sitelinks}")
