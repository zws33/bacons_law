import json
from collections.abc import Iterable, Iterator
from dataclasses import asdict
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


def transform(cfg: BuildConfig) -> TransformStats:
    edge_count = 0
    movies: set[str] = set()
    actors: set[str] = set()

    def _edges() -> Iterator[Edge]:
        """Stream partition by partition; a full-range build never holds every edge at once."""
        nonlocal edge_count
        for rows in _load_rows():
            for e in _build_edge_list(rows=rows, min_cast=cfg.min_cast, cast_cap=cfg.cast_cap):
                edge_count += 1
                movies.add(e.movie)
                actors.add(e.actor)
                yield e

    _write_edges(_edges())
    return TransformStats(edge_count, len(movies), len(actors))


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


def _load_rows():
    for path in paths.RAW_DIR.glob("films-*.json"):
        try:
            data = CachePayload.model_validate(read_json(path))
        except ValidationError as e:
            raise ValueError(f"Failed to load {path}: {e}") from e
        yield data.rows


def _cap_cast(cast: dict[str, Actor], cap: int):
    return sorted(cast.values(), key=lambda actor: (-actor.sitelinks, int(actor.qid[1:])))[:cap]


def _build_edge_list(rows: list[WikidataRow], min_cast: int, cast_cap: int) -> list[Edge]:
    """Transform a list of WikidataRow objects into a list of Edge objects."""

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
                    actor=actor.qid,
                    actor_label=actor.label,
                )
            )
    edges.sort(key=lambda e: (e.movie, e.actor))
    return edges
