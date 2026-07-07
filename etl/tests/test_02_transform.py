"""Stage 2 — transform: load_films, cap_cast, films_to_edges (all pure)."""

from _harness import make_film, require, row, write_raw


def _actors_of(edges, movie):
    return sorted(e.actor for e in edges if e.movie == movie)


def test_cap_keeps_top_n_by_actor_sitelinks():
    films_to_edges = require("transform", "films_to_edges")
    BuildConfig = require("config", "BuildConfig")
    f = make_film("Q1", ("Q10", 10), ("Q11", 90), ("Q12", 50))
    edges = films_to_edges({"Q1": f}, BuildConfig(min_cast=1, cast_cap=2))
    assert _actors_of(edges, "Q1") == ["Q11", "Q12"], "keep the two highest-sitelink actors"


def test_cap_ties_break_by_qid_for_determinism():
    """The single most important line in the stage: key=(-sitelinks, qid)."""
    cap_cast = require("transform", "cap_cast")
    f = make_film("Q1", ("Q11", 50), ("Q10", 50), ("Q12", 50))  # all tied
    kept = [a.qid for a in cap_cast(f.cast, 2)]
    assert kept == ["Q10", "Q11"], (
        "when sitelink counts tie, break by QID so two builds agree. "
        "Sort with key=lambda a: (-a.sitelinks, a.qid)."
    )


def test_min_cast_floor_is_a_strict_boundary():
    films_to_edges = require("transform", "films_to_edges")
    BuildConfig = require("config", "BuildConfig")
    below = make_film("Q1", ("Q10", 9), ("Q11", 9))                 # 2 cast → dropped
    at = make_film("Q2", ("Q20", 9), ("Q21", 9), ("Q22", 9))        # 3 cast → kept
    edges = films_to_edges({"Q1": below, "Q2": at}, BuildConfig(min_cast=3, cast_cap=15))
    assert _actors_of(edges, "Q1") == [], "a film below min_cast must be dropped entirely"
    assert len(_actors_of(edges, "Q2")) == 3, "a film at exactly min_cast is kept"


def test_floor_counts_distinct_cast_then_caps():
    """Apply the floor to DISTINCT cast, then cap — not the other way round."""
    films_to_edges = require("transform", "films_to_edges")
    BuildConfig = require("config", "BuildConfig")
    f = make_film("Q1", ("Q10", 30), ("Q11", 20), ("Q12", 10))     # 3 distinct
    edges = films_to_edges({"Q1": f}, BuildConfig(min_cast=3, cast_cap=2))
    # passes the floor (3 ≥ 3), THEN capped to 2 highest
    assert _actors_of(edges, "Q1") == ["Q10", "Q11"]


def test_duplicate_rows_across_partitions_collapse():
    load_films = require("transform", "load_films")
    import pathlib
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        directory = pathlib.Path(d)
        # same (film, actor) appears in two year files
        write_raw(directory, 1994, [row("Q1", "Q10")])
        write_raw(directory, 1995, [row("Q1", "Q10")])
        films = load_films(sorted(directory.glob("films-*.json")))
    assert list(films["Q1"].cast) == ["Q10"], (
        "the same actor across two partitions must count once. "
        "Key the cast by QID (a dict) so duplicates collapse."
    )


def test_edges_are_emitted_in_deterministic_order():
    films_to_edges = require("transform", "films_to_edges")
    BuildConfig = require("config", "BuildConfig")
    films = {
        "Q2": make_film("Q2", ("Q30", 5), ("Q10", 5), ("Q20", 5)),
        "Q1": make_film("Q1", ("Q40", 5), ("Q05", 5), ("Q99", 5)),
    }
    edges = films_to_edges(films, BuildConfig(min_cast=1, cast_cap=15))
    keys = [(e.movie, e.actor) for e in edges]
    assert keys == sorted(keys), (
        "sort the edge list by (movie, actor) before returning it, so the output "
        "is byte-reproducible regardless of dict iteration order."
    )
