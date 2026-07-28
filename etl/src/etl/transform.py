from collections import defaultdict
from dataclasses import asdict
from typing import NamedTuple

from pydantic import ValidationError

import etl.paths as paths
from etl.config import BuildConfig
from etl.io import read_json, write_jsonl
from etl.models import Actor, CachePayload, Edge, WikidataRow


class TransformStats(NamedTuple):
    edges: int
    movies: int
    actors: int


def transform(cfg: BuildConfig) -> TransformStats:
    rows = _load_rows()
    edges = _build_edge_list(rows=rows, min_cast=cfg.min_cast, cast_cap=cfg.cast_cap)
    _write_edges(edges)
    movies = {e.movie for e in edges}
    actors = {e.actor for e in edges}
    return TransformStats(len(edges), len(movies), len(actors))


def _write_edges(edges: list[Edge]) -> None:
    paths.INTERIM_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(paths.edges_path(), [asdict(e) for e in edges])


def _load_rows() -> list[WikidataRow]:
    rows: list[WikidataRow] = []
    for path in paths.RAW_DIR.glob("films-*.json"):
        try:
            data = CachePayload.model_validate(read_json(path))
        except ValidationError as e:
            raise ValueError(f"Failed to load {path}: {e}") from e
        rows.extend(data.rows)
    return rows


def _cap_cast(cast: dict[str, Actor], cap: int) -> list[Actor]:
    return sorted(cast.values(), key=lambda a: (-a.sitelinks, int(a.qid[1:])))[:cap]


def _build_edge_list(rows: list[WikidataRow], min_cast: int, cast_cap: int) -> list[Edge]:
    """Transform a list of WikidataRow objects into a list of Edge objects."""

    film_labels: dict[str, str] = {}
    cast_by_film: dict[str, dict[str, Actor]] = defaultdict(dict)
    for row in rows:
        film_labels.setdefault(row["film"], row["film_label"])
        qid = row["actor"]
        cast_by_film[row["film"]].setdefault(
            qid, Actor(qid=qid, label=row["actor_label"], sitelinks=row["actor_sitelinks"])
        )

    edges: list[Edge] = []
    for film, cast in cast_by_film.items():
        if len(cast) < min_cast:
            continue
        for actor in _cap_cast(cast, cast_cap):
            edges.append(
                Edge(
                    movie=film,
                    movie_label=film_labels[film],
                    actor=actor.qid,
                    actor_label=actor.label,
                )
            )
    edges.sort(key=lambda e: (e.movie, e.actor))
    return edges
