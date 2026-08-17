import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from typing import NamedTuple

from pydantic import ValidationError

import etl.paths as paths
from etl.config import BuildConfig
from etl.io import read_json
from etl.models import Actor, CachePayload, Edge, Film, WikidataRow


class TransformStats(NamedTuple):
    edges: int
    movies: int
    actors: int


@dataclass
class _Counter:
    edges: int = 0
    movies: set[str] = field(default_factory=set)
    actors: set[str] = field(default_factory=set)


def transform(cfg: BuildConfig) -> TransformStats:
    counter = _Counter()
    _write_edges(_edges(cfg.min_cast, cfg.cast_cap, counter))
    return TransformStats(counter.edges, len(counter.movies), len(counter.actors))


def _edges(min_cast: int, cast_cap: int, counter: _Counter) -> Iterator[Edge]:
    """Stream partition by partition; a full-range build never holds every edge at once.

    A film is emitted from the FIRST partition it appears in and skipped thereafter. P577 is
    multi-valued, so a festival premiere and a wide release put the same film in two years;
    without this, a film would carry whichever year iterated last (emit's entities loop is
    last-write-wins). _load_rows sorts, so first-seen is the earliest release year.

    Dropping the repeat is safe because the cast comes from wdt:P161, which is
    date-independent — the second partition carries the same rows.
    """
    seen: set[str] = set()
    for payload in _load_rows():
        fresh = [row for row in payload.rows if row["film"] not in seen]
        for e in _build_edge_list(
            rows=fresh, year=payload.year, min_cast=min_cast, cast_cap=cast_cap
        ):
            counter.edges += 1
            counter.movies.add(e.movie)
            counter.actors.add(e.actor)
            yield e
        # Films the min_cast gate dropped join `seen` too: the repeat partition carries the
        # same cast, so it would be dropped there identically.
        seen.update(row["film"] for row in payload.rows)


def _write_edges(edges: Iterable[Edge]) -> None:
    """The interim-file writer. transform() streams a generator through it, emit's tests
    pass a list — one formatter, so the two stages can't drift on framing."""
    paths.INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    path = paths.edges_path()
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("w") as f:
            for e in edges:
                f.write(json.dumps(asdict(e)) + "\n")
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _load_rows() -> Iterator[CachePayload]:
    """Yield each cached partition whole — `year` is as load-bearing as `rows` now.

    The payload's own `year` is trusted over the filename: it is the validated record, and
    extract wrote it from the same loop variable the query was templated with.
    """
    # sorted(), because Path.glob yields in os.scandir order — filesystem-dependent, not
    # lexicographic. Over films-YYYY.json, sorting is chronological, so partitions arrive
    # oldest first, edges.jsonl is reproducible across machines, and _edges' first-seen-wins
    # dedupe resolves to the earliest release year. emit._query_date_range sorts this glob too.
    for path in sorted(paths.RAW_DIR.glob("films-*.json")):
        try:
            data = CachePayload.model_validate(read_json(path))
        except ValidationError as e:
            raise ValueError(f"Failed to load {path}: {e}") from e
        yield data


def _cap_cast(cast: dict[str, Actor], cap: int):
    return sorted(cast.values(), key=lambda actor: (-actor.sitelinks, int(actor.qid[1:])))[:cap]


def _build_edge_list(
    rows: list[WikidataRow], year: int, min_cast: int, cast_cap: int
) -> list[Edge]:
    """Transform a list of WikidataRow objects into a list of Edge objects.

    `year` is the partition's — every film in the file satisfies YEAR(?date) = year, so it is
    a property of the batch rather than something to thread through the per-film accumulator.
    """

    cast_by_film: dict[str, Film] = {}
    for row in rows:
        film = cast_by_film.setdefault(
            row["film"],
            Film(qid=row["film"], label=row["film_label"], sitelinks=row["film_sitelinks"]),
        )
        film.cast[row["actor"]] = Actor(
            qid=row["actor"],
            label=row["actor_label"],
            sitelinks=row["actor_sitelinks"],
        )

    edges: list[Edge] = []
    for film in cast_by_film.values():
        if len(film.cast) < min_cast:
            continue
        for actor in _cap_cast(film.cast, cast_cap):
            edges.append(
                Edge(
                    movie=film.qid,
                    movie_label=film.label,
                    movie_sitelinks=film.sitelinks,
                    movie_year=year,
                    actor=actor.qid,
                    actor_label=actor.label,
                    actor_sitelinks=actor.sitelinks,
                )
            )
    edges.sort(key=lambda e: (e.movie, e.actor))
    return edges
