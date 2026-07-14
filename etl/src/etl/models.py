from dataclasses import dataclass, field
from typing import TypedDict


@dataclass(frozen=True)
class Actor:
    qid: str
    label: str
    sitelinks: int


@dataclass
class Film:
    qid: str
    label: str
    sitelinks: int
    # actor_qid -> Actor. A dict so duplicate rows across year partitions collapse for free.
    cast: dict[str, Actor] = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    movie: str
    movie_label: str
    actor: str
    actor_label: str


class WikidataRow(TypedDict):
    """One flattened film-actor row as fetched from WDQS and cached as JSON."""

    film: str
    film_label: str
    film_sitelinks: int
    actor: str
    actor_label: str
    actor_sitelinks: int


class CachePayload(TypedDict):
    """Payload structure for cached raw data."""

    year: int
    fetched_at: str
    endpoint: str
    min_sitelinks: int
    require_enwiki: bool
    row_count: int
    rows: list[WikidataRow]
