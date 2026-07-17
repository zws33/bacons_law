from dataclasses import asdict

from pydantic import ValidationError

import etl.paths as paths
from etl.config import BuildConfig
from etl.io import read_json, write_jsonl
from etl.models import Actor, CachePayload, Edge, Film, WikidataRow


def transform(cfg: BuildConfig) -> int:
    rows = _load_rows()
    edges = _build_edge_list(rows=rows, min_cast=cfg.min_cast, cast_cap=cfg.cast_cap)
    _write_edges(edges)
    return len(edges)


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
    # sitelinks desc; ties broken by numeric QID asc (Q9 before Q10) so the cut is
    # deterministic and matches intuition rather than lexicographic string order.
    return sorted(cast.values(), key=lambda a: (-a.sitelinks, int(a.qid[1:])))[:cap]


def _build_edge_list(rows: list[WikidataRow], min_cast: int, cast_cap: int) -> list[Edge]:
    """Transform a list of WikidataRow objects into a list of Edge objects."""

    films: dict[str, Film] = {}
    for row in rows:
        if row["film"] not in films:
            films[row["film"]] = Film(
                qid=row["film"], label=row["film_label"], sitelinks=row["film_sitelinks"]
            )
        films[row["film"]].cast.setdefault(
            row["actor"],
            Actor(
                qid=row["actor"],
                label=row["actor_label"],
                sitelinks=row["actor_sitelinks"],
            ),
        )
    # min_cast gates on the FULL cast (a source-data quality filter); cast_cap below
    # then limits the emitted degree per film. The two knobs are independent, so a film
    # can pass this gate yet emit fewer than min_cast edges when cast_cap < min_cast.
    final: dict[str, Film] = {
        key: film for key, film in films.items() if len(film.cast) >= min_cast
    }

    edges: list[Edge] = []
    for film in final.values():
        capped_cast_list = _cap_cast(cast=film.cast, cap=cast_cap)
        for actor in capped_cast_list:
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
