from etl.models import Actor, Edge, Film, WikidataRow


def build_edge_list(rows: list[WikidataRow], min_cast: int, cast_cap: int) -> list[Edge]:
    """Transform a cached payload into a list of Edge objects."""

    films_dict: dict[str, Film] = {}
    for row in rows:
        if row["film"] not in films_dict:
            films_dict[row["film"]] = Film(
                qid=row["film"], label=row["film_label"], sitelinks=row["film_sitelinks"]
            )
        films_dict[row["film"]].cast.setdefault(
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
        key: film for key, film in films_dict.items() if len(film.cast) >= min_cast
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


def _cap_cast(cast: dict[str, Actor], cap: int) -> list[Actor]:
    # sitelinks desc; ties broken by numeric QID asc (Q9 before Q10) so the cut is
    # deterministic and matches intuition rather than lexicographic string order.
    return sorted(cast.values(), key=lambda a: (-a.sitelinks, int(a.qid[1:])))[:cap]
