from collections import defaultdict
from dataclasses import asdict
from typing import NamedTuple

from pydantic import ValidationError

import etl.paths as paths
from etl.config import BuildConfig
from etl.io import read_json, write_jsonl
from etl.models import CachePayload, Edge, WikidataRow


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


def _cap_cast(cast: dict[str, int], cap: int):
    return sorted(cast.items(), key=lambda actor: (-actor[1], int(actor[0][1:])))[:cap]


def _build_edge_list(rows: list[WikidataRow], min_cast: int, cast_cap: int) -> list[Edge]:
    """Transform a list of WikidataRow objects into a list of Edge objects."""

    cast_by_film: dict[str, dict[str, int]] = defaultdict(dict)
    for row in rows:
        cast_by_film[row["film"]][row["actor"]] = row["actor_sitelinks"]

    edges: list[Edge] = []
    for film, cast in cast_by_film.items():
        if len(cast) < min_cast:
            continue
        for actor in _cap_cast(cast, cast_cap):
            edges.append(Edge(movie=film, actor=actor[0]))
    edges.sort(key=lambda e: (e.movie, e.actor))
    return edges
