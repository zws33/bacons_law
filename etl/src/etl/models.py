from dataclasses import dataclass, field
from typing import TypedDict

from pydantic import BaseModel, model_validator


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
    cast: dict[str, Actor] = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    movie: str
    movie_label: str
    actor: str
    actor_label: str


QueryDateRange = TypedDict("QueryDateRange", {"from": str | None, "to": str | None})


class ManifestConfig(TypedDict):
    """The gameplay dials that produced this graph. These travel WITH the data — the
    artifact is reproducible only if it says what went into it."""

    min_sitelinks: int
    min_cast: int
    cast_cap: int
    year_from: int
    year_to: int


class ManifestCounts(TypedDict):
    n_movies: int
    n_actors: int
    n_edges: int


class Manifest(TypedDict):
    """Self-describing build record written beside graph.json. A plain shape, not a
    validated one: it is only ever constructed here and written out, never parsed back.
    basedpyright enforces the fields; json.dumps(sort_keys=True) handles determinism."""

    schema_version: int
    version: str
    source: str
    query_date: QueryDateRange
    generated_at: str
    config: ManifestConfig
    counts: ManifestCounts


class WikidataRow(TypedDict):
    """One flattened film-actor row as fetched from WDQS and cached as JSON."""

    film: str
    film_label: str
    film_sitelinks: int
    actor: str
    actor_label: str
    actor_sitelinks: int


class CacheHeader(BaseModel):
    """Everything about a cached partition EXCEPT its rows.

    Validating the rows means running WikidataRow over ~600k dicts; the two callers that
    only need provenance or the config fingerprint (extract._cache_is_valid,
    emit._query_date_range) run on every build and don't care about row contents. Pydantic
    ignores extra keys by default, so this validates a full payload dict and drops `rows`.
    """

    year: int
    fetched_at: str
    endpoint: str
    min_sitelinks: int
    row_count: int


class CachePayload(CacheHeader):
    """A cached partition, rows included. The full-fidelity read transform uses."""

    rows: list[WikidataRow]

    @model_validator(mode="after")
    def _row_count_matches(self):
        if self.row_count != len(self.rows):
            raise ValueError(f"row_count {self.row_count} != {len(self.rows)}")
        return self
