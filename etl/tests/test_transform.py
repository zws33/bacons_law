"""Tests for the transform stage (etl.transform) — pure functions only.

Two seams are tested here:
  * build_edge_list — the main entry point that filters films by min_cast,
    caps each film's cast, and emits sorted Edge objects.
  * _cap_cast — the cast capping helper that sorts by sitelinks (desc) then numeric qid (asc).

All tests are deterministic and network-free.
"""

from etl.models import Actor, WikidataRow
from etl.transform import _build_edge_list, _cap_cast

# --- fixtures / helpers -----------------------------------------------------------


def _row(
    film: str = "Q1",
    film_label: str = "Film One",
    film_sitelinks: int = 100,
    actor: str = "Q10",
    actor_label: str = "Actor Ten",
    actor_sitelinks: int = 50,
) -> WikidataRow:
    """Factory for a single WikidataRow."""
    return WikidataRow(
        film=film,
        film_label=film_label,
        film_sitelinks=film_sitelinks,
        actor=actor,
        actor_label=actor_label,
        actor_sitelinks=actor_sitelinks,
    )


# --- _cap_cast ------------------------------------------------------------------


def test_cap_cast_empty_dict():
    """Empty cast returns empty list."""
    assert _cap_cast({}, cap=5) == []


def test_cap_cast_single_actor():
    """Single actor is returned as-is."""
    cast = {"Q10": Actor(qid="Q10", label="Actor Ten", sitelinks=50)}
    result = _cap_cast(cast, cap=5)
    assert result == [Actor(qid="Q10", label="Actor Ten", sitelinks=50)]


def test_cap_cast_sorts_by_sitelinks_desc():
    """Actors are sorted by sitelinks descending."""
    cast = {
        "Q1": Actor(qid="Q1", label="A", sitelinks=10),
        "Q2": Actor(qid="Q2", label="B", sitelinks=100),
        "Q3": Actor(qid="Q3", label="C", sitelinks=50),
    }
    result = _cap_cast(cast, cap=10)
    assert [a.qid for a in result] == ["Q2", "Q3", "Q1"]


def test_cap_cast_ties_broken_by_qid_asc():
    """When sitelinks are equal, sort by qid ascending."""
    cast = {
        "Q3": Actor(qid="Q3", label="C", sitelinks=50),
        "Q1": Actor(qid="Q1", label="A", sitelinks=50),
        "Q2": Actor(qid="Q2", label="B", sitelinks=50),
    }
    result = _cap_cast(cast, cap=10)
    assert [a.qid for a in result] == ["Q1", "Q2", "Q3"]


def test_cap_cast_ties_broken_by_numeric_qid_not_lexicographic():
    """Equal sitelinks: QIDs sort numerically (Q9 before Q10), not as strings."""
    cast = {
        "Q10": Actor(qid="Q10", label="A", sitelinks=50),
        "Q9": Actor(qid="Q9", label="B", sitelinks=50),
        "Q100": Actor(qid="Q100", label="C", sitelinks=50),
    }
    result = _cap_cast(cast, cap=10)
    assert [a.qid for a in result] == ["Q9", "Q10", "Q100"]


def test_cap_cast_respects_cap():
    """Only top N actors by sitelinks are returned."""
    cast = {f"Q{i}": Actor(qid=f"Q{i}", label=f"Actor {i}", sitelinks=100 - i) for i in range(10)}
    result = _cap_cast(cast, cap=3)
    assert len(result) == 3
    assert [a.qid for a in result] == ["Q0", "Q1", "Q2"]


def test_cap_cast_cap_larger_than_cast():
    """If cap is larger than cast size, all actors are returned."""
    cast = {
        "Q1": Actor(qid="Q1", label="A", sitelinks=50),
        "Q2": Actor(qid="Q2", label="B", sitelinks=25),
    }
    result = _cap_cast(cast, cap=10)
    assert len(result) == 2


def test_cap_cast_cap_zero():
    """Cap of zero returns empty list."""
    cast = {"Q1": Actor(qid="Q1", label="A", sitelinks=50)}
    assert _cap_cast(cast, cap=0) == []


# --- build_edge_list ------------------------------------------------------


def test_transform_empty_rows():
    """Empty input yields empty edges."""
    assert _build_edge_list([], min_cast=1, cast_cap=10) == []


def test_transform_single_row_below_min_cast():
    """Film with cast below min_cast is filtered out."""
    rows = [_row()]
    assert _build_edge_list(rows, min_cast=2, cast_cap=10) == []


def test_transform_single_row_meets_min_cast():
    """Film with cast exactly at min_cast is included."""
    rows = [_row()]
    result = _build_edge_list(rows, min_cast=1, cast_cap=10)
    assert len(result) == 1
    assert result[0].movie == "Q1"
    assert result[0].movie_label == "Film One"
    assert result[0].actor == "Q10"
    assert result[0].actor_label == "Actor Ten"


def test_transform_multiple_rows_same_film():
    """Multiple rows for the same film are collapsed into one Film with combined cast."""
    rows = [
        _row(film="Q1", actor="Q10", actor_label="Actor Ten"),
        _row(film="Q1", actor="Q20", actor_label="Actor Twenty"),
        _row(film="Q1", actor="Q30", actor_label="Actor Thirty"),
    ]
    result = _build_edge_list(rows, min_cast=2, cast_cap=10)
    assert len(result) == 3  # 3 edges for one film with 3 actors
    film_qids = {e.movie for e in result}
    assert film_qids == {"Q1"}
    actor_qids = {e.actor for e in result}
    assert actor_qids == {"Q10", "Q20", "Q30"}


def test_transform_multiple_films():
    """Multiple films each produce their own edges."""
    rows = [
        _row(film="Q1", actor="Q10"),
        _row(film="Q2", actor="Q20"),
        _row(film="Q2", actor="Q21"),
    ]
    result = _build_edge_list(rows, min_cast=1, cast_cap=10)
    assert len(result) == 3
    film_qids = {e.movie for e in result}
    assert film_qids == {"Q1", "Q2"}


def test_transform_filters_film_below_min_cast():
    """Films with cast count below min_cast are excluded."""
    rows = [
        _row(film="Q1", actor="Q10"),  # film Q1 has only 1 actor
        _row(film="Q2", actor="Q20"),
        _row(film="Q2", actor="Q21"),  # film Q2 has 2 actors
    ]
    result = _build_edge_list(rows, min_cast=2, cast_cap=10)
    assert len(result) == 2
    assert all(e.movie == "Q2" for e in result)


def test_transform_applies_cast_cap():
    """Each film's cast is capped at cast_cap."""
    rows = [_row(film="Q1", actor=f"Q{i}", actor_sitelinks=100 - i) for i in range(10)]
    result = _build_edge_list(rows, min_cast=1, cast_cap=3)
    assert len(result) == 3
    actor_qids = [e.actor for e in result]
    # Sorted by sitelinks desc, so Q0 (100), Q1 (99), Q2 (98) should be first
    assert actor_qids == ["Q0", "Q1", "Q2"]


def test_transform_edges_sorted_by_movie_then_actor():
    """Edges are sorted by movie qid, then actor qid."""
    rows = [
        _row(film="Q2", actor="Q21"),
        _row(film="Q1", actor="Q11"),
        _row(film="Q2", actor="Q20"),
        _row(film="Q1", actor="Q10"),
    ]
    result = _build_edge_list(rows, min_cast=1, cast_cap=10)
    movie_actor_pairs = [(e.movie, e.actor) for e in result]
    assert movie_actor_pairs == [
        ("Q1", "Q10"),
        ("Q1", "Q11"),
        ("Q2", "Q20"),
        ("Q2", "Q21"),
    ]


def test_transform_preserves_film_label():
    """Film labels are preserved from input rows."""
    rows = [_row(film="Q1", film_label="The Matrix", actor="Q10")]
    result = _build_edge_list(rows, min_cast=1, cast_cap=10)
    assert result[0].movie_label == "The Matrix"


def test_transform_preserves_actor_label():
    """Actor labels are preserved from input rows."""
    rows = [_row(actor="Q10", actor_label="Keanu Reeves")]
    result = _build_edge_list(rows, min_cast=1, cast_cap=10)
    assert result[0].actor_label == "Keanu Reeves"


def test_transform_duplicate_rows_same_film_same_actor():
    """Duplicate rows for the same film+actor are deduplicated."""
    rows = [
        _row(film="Q1", actor="Q10"),
        _row(film="Q1", actor="Q10"),  # duplicate
        _row(film="Q1", actor="Q20"),
    ]
    result = _build_edge_list(rows, min_cast=1, cast_cap=10)
    assert len(result) == 2
    actor_qids = {e.actor for e in result}
    assert actor_qids == {"Q10", "Q20"}


def test_transform_duplicate_rows_different_actor_labels():
    """If duplicate actor rows have different labels, the first one wins (setdefault)."""
    rows = [
        _row(film="Q1", actor="Q10", actor_label="First Name"),
        _row(film="Q1", actor="Q10", actor_label="Second Name"),
    ]
    result = _build_edge_list(rows, min_cast=1, cast_cap=10)
    # setdefault() only sets if key doesn't exist, so first label is kept
    assert len(result) == 1
    assert result[0].actor == "Q10"
    assert result[0].actor_label == "First Name"


def test_transform_mixed_min_cast_filtering():
    """Complex case: multiple films, some pass min_cast, some don't."""
    rows = [
        # Q1: 3 actors -> included (>= 2)
        _row(film="Q1", actor="Q10"),
        _row(film="Q1", actor="Q11"),
        _row(film="Q1", actor="Q12"),
        # Q2: 1 actor -> excluded (< 2)
        _row(film="Q2", actor="Q20"),
        # Q3: 2 actors -> included (>= 2)
        _row(film="Q3", actor="Q30"),
        _row(film="Q3", actor="Q31"),
    ]
    result = _build_edge_list(rows, min_cast=2, cast_cap=10)
    film_qids = {e.movie for e in result}
    assert film_qids == {"Q1", "Q3"}
    assert len(result) == 5  # 3 from Q1 + 2 from Q3


def test_transform_with_cast_cap_and_min_cast():
    """Both min_cast and cast_cap are applied together."""
    rows = [
        # Q1: 5 actors, cap at 3, meets min_cast=2 -> included with 3 edges
        _row(film="Q1", actor=f"Q{i}", actor_sitelinks=100 - i)
        for i in range(5)
    ] + [
        # Q2: 1 actor, below min_cast=2 -> excluded
        _row(film="Q2", actor="Q20"),
    ]
    result = _build_edge_list(rows, min_cast=2, cast_cap=3)
    assert len(result) == 3
    assert all(e.movie == "Q1" for e in result)
    actor_qids = [e.actor for e in result]
    assert actor_qids == ["Q0", "Q1", "Q2"]


def test_transform_cast_cap_below_min_cast():
    """min_cast gates the full cast; cast_cap < min_cast still emits only cast_cap edges.

    A film with 4 cast passes min_cast=4, then cast_cap=2 trims the emitted edges to 2 —
    the gate and the degree cap are independent knobs.
    """
    rows = [_row(film="Q1", actor=f"Q{i}", actor_sitelinks=100 - i) for i in range(4)]
    result = _build_edge_list(rows, min_cast=4, cast_cap=2)
    assert len(result) == 2
    assert [e.actor for e in result] == ["Q0", "Q1"]
