"""Tests for the transform stage (etl.transform) — pure functions only.

Three seams are tested here:
  * build_edge_list — the main entry point that filters films by min_cast,
    caps each film's cast, and emits sorted Edge objects.
  * _cap_cast — the cast capping helper that sorts by sitelinks (desc) then numeric qid (asc).
  * _load_rows — partition order, which decides the interim file's line order.

All tests are deterministic and network-free.
"""

import json
from pathlib import Path

import pytest

import etl.paths as paths
from etl import extract
from etl.config import BuildConfig
from etl.models import Actor, WikidataRow
from etl.transform import _build_edge_list, _cap_cast, _load_rows

# --- fixtures / helpers -----------------------------------------------------------


def _row(
    film: str = "Q1",
    film_sitelinks: int = 100,
    actor: str = "Q10",
    actor_sitelinks: int = 50,
    film_label: str = "",
    actor_label: str = "",
) -> WikidataRow:
    """Factory for a single WikidataRow. Labels default to the QID — the same fallback
    sparql._flatten applies for an unbound OPTIONAL — so the edge assertions below stay
    about QIDs, which is the part transform's policy actually operates on."""
    return WikidataRow(
        film=film,
        film_label=film_label or film,
        film_sitelinks=film_sitelinks,
        actor=actor,
        actor_label=actor_label or actor,
        actor_sitelinks=actor_sitelinks,
    )


def _cast(*pairs: tuple[str, int]) -> dict[str, Actor]:
    """qid -> Actor, the shape _cap_cast ranks. Labels are irrelevant to the ordering."""
    return {qid: Actor(qid=qid, label=qid, sitelinks=n) for qid, n in pairs}


# --- _cap_cast ------------------------------------------------------------------


def test_cap_cast_empty_dict():
    """Empty cast returns empty list."""
    assert _cap_cast({}, cap=5) == []


def test_cap_cast_single_actor():
    """Single actor is returned as-is."""
    result = _cap_cast(_cast(("Q10", 50)), cap=5)
    assert [a.qid for a in result] == ["Q10"]


def test_cap_cast_sorts_by_sitelinks_desc():
    """Actors are sorted by sitelinks descending."""
    result = _cap_cast(_cast(("Q1", 10), ("Q2", 100), ("Q3", 50)), cap=10)
    assert [a.qid for a in result] == ["Q2", "Q3", "Q1"]


def test_cap_cast_ties_broken_by_qid_asc():
    """When sitelinks are equal, sort by qid ascending."""
    result = _cap_cast(_cast(("Q3", 50), ("Q1", 50), ("Q2", 50)), cap=10)
    assert [a.qid for a in result] == ["Q1", "Q2", "Q3"]


def test_cap_cast_ties_broken_by_numeric_qid_not_lexicographic():
    """Equal sitelinks: QIDs sort numerically (Q9 before Q10), not as strings."""
    result = _cap_cast(_cast(("Q10", 50), ("Q9", 50), ("Q100", 50)), cap=10)
    assert [a.qid for a in result] == ["Q9", "Q10", "Q100"]


def test_cap_cast_respects_cap():
    """Only top N actors by sitelinks are returned."""
    result = _cap_cast(_cast(*((f"Q{i}", 100 - i) for i in range(10))), cap=3)
    assert [a.qid for a in result] == ["Q0", "Q1", "Q2"]


def test_cap_cast_cap_larger_than_cast():
    """If cap is larger than cast size, all actors are returned."""
    result = _cap_cast(_cast(("Q1", 50), ("Q2", 25)), cap=10)
    assert len(result) == 2


def test_cap_cast_cap_zero():
    """Cap of zero returns empty list."""
    assert _cap_cast(_cast(("Q1", 50)), cap=0) == []


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
    assert result[0].actor == "Q10"


def test_transform_multiple_rows_same_film():
    """Multiple rows for the same film are collapsed into one Film with combined cast."""
    rows = [
        _row(film="Q1", actor="Q10"),
        _row(film="Q1", actor="Q20"),
        _row(film="Q1", actor="Q30"),
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


def test_transform_duplicate_rows_same_film_same_actor():
    """Duplicate rows for the same film+actor are deduplicated (last sitelinks wins)."""
    rows = [
        _row(film="Q1", actor="Q10"),
        _row(film="Q1", actor="Q10"),  # duplicate
        _row(film="Q1", actor="Q20"),
    ]
    result = _build_edge_list(rows, min_cast=1, cast_cap=10)
    assert len(result) == 2
    actor_qids = {e.actor for e in result}
    assert actor_qids == {"Q10", "Q20"}


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


# --- _load_rows -----------------------------------------------------------------


@pytest.fixture
def raw_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    monkeypatch.setattr(paths, "RAW_DIR", raw)
    return raw


def _write_partition(raw: Path, year: int, rows: list[WikidataRow]) -> None:
    (raw / f"films-{year}.json").write_text(
        json.dumps(
            {
                "year": year,
                "fetched_at": "2020-01-01T00:00:00+00:00",
                "endpoint": BuildConfig().endpoint,
                "min_sitelinks": 5,
                "query_version": extract.QUERY_VERSION,
                "row_count": len(rows),
                "rows": rows,
            }
        )
    )


def test_load_rows_yields_partitions_oldest_first(raw_dir: Path):
    """Path.glob yields in os.scandir order, which is filesystem-dependent. Sorting makes
    the interim file's line order reproducible across machines, and over films-YYYY.json
    lexicographic order is chronological."""
    _write_partition(raw_dir, 2016, [_row(film="Q3")])
    _write_partition(raw_dir, 1994, [_row(film="Q1")])
    _write_partition(raw_dir, 2005, [_row(film="Q2")])

    assert [rows[0]["film"] for rows in _load_rows()] == ["Q1", "Q2", "Q3"]


def test_load_rows_empty_dir_yields_nothing(raw_dir: Path):
    assert list(_load_rows()) == []
