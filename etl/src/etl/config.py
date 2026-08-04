from dataclasses import dataclass


@dataclass(frozen=True)
class BuildConfig:
    min_sitelinks: int = 5
    min_cast: int = 3
    cast_cap: int = 15
    user_agent: str = "bacons-law-etl/0.1 (zach.smith33@gmail.com)"
    endpoint: str = "https://qlever.dev/api/wikidata"
    year_from: int = 1925
    year_to: int = 2026

    def __post_init__(self) -> None:
        if self.year_from > self.year_to:
            raise ValueError(f"year_from {self.year_from} > year_to {self.year_to}")
        if self.cast_cap < 1:
            raise ValueError(f"cast_cap must be >= 1, got {self.cast_cap}")
        if self.min_cast < 1:
            raise ValueError(f"min_cast must be >= 1, got {self.min_cast}")
        if self.min_sitelinks < 0:
            raise ValueError(f"min_sitelinks must be >= 0, got {self.min_sitelinks}")
