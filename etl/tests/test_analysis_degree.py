"""Tests for analysis.degree_distribution — investigation 001's measurement code.

Deliberately NOT full coverage of a one-off analysis script. Tests go only where a wrong
answer would be SILENT — a plausible-looking number that no one would question:

  * cross-partition dedupe (P577 is multi-valued, so films recur across year files)
  * node classification, which must ignore entities[qid]["type"]
  * the genuine / cap-induced split, which decides whether any remedy is warranted
  * decile bucketing under ties, which H4's verdict depends on

Test 2 is the load-bearing one: if cross-partition dedupe breaks, every degree-1 actor whose
film spans two partitions is misfiled as cap-induced, inverting H1 with no visible symptom.

All tests are deterministic and network-free.
"""

import json
from pathlib import Path

import pytest
from analysis.degree_distribution import (
    decile_buckets,
    m1_degree_distribution,
    m2_genuine_vs_cap_induced,
    m5_both_map_qids,
    scan_raw,
)

import etl.paths as paths

# --- fixtures / helpers -----------------------------------------------------------


def _row(
    film: str,
    actor: str,
    film_sitelinks: int = 100,
    actor_sitelinks: int = 50,
) -> dict[str, object]:
    """One flattened WikidataRow as extract caches it. Labels default to the QID, matching
    sparql._flatten's fallback — these assertions are about QIDs, not display text."""
    return {
        "film": film,
        "film_label": film,
        "film_sitelinks": film_sitelinks,
        "actor": actor,
        "actor_label": actor,
        "actor_sitelinks": actor_sitelinks,
    }


def _write_partition(year: int, rows: list[dict[str, object]]) -> None:
    """Write a raw partition the way extract does, so CachePayload validates it."""
    paths.RAW_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "year": year,
        "fetched_at": "2026-08-06T00:00:00+00:00",
        "endpoint": "https://qlever.dev/api/wikidata",
        "min_sitelinks": 5,
        "query_version": 2,
        "row_count": len(rows),
        "rows": rows,
    }
    (paths.RAW_DIR / f"films-{year}.json").write_text(json.dumps(payload))


@pytest.fixture
def raw_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point paths.RAW_DIR at a temp dir so partitions written here never touch data/raw/."""
    target = tmp_path / "raw"
    target.mkdir()
    monkeypatch.setattr(paths, "RAW_DIR", target)
    return target


# --- cross-partition dedupe -------------------------------------------------------


def test_film_in_two_partitions_counted_once(raw_dir: Path) -> None:
    """A film with two publication dates appears in two partitions carrying identical cast.

    Its pre-cap cast count must be the distinct cast, not the sum across partitions — the
    property scan_raw's seen_films guard exists to preserve.
    """
    rows = [_row("Q1", "Q10"), _row("Q1", "Q11"), _row("Q1", "Q12")]
    _write_partition(1994, rows)
    _write_partition(1995, rows)

    agg = scan_raw(movie_qids={"Q1"}, actor_qids={"Q10", "Q11", "Q12"}, degree1_qids=set())

    assert agg["film_raw_cast_count"]["Q1"] == 3
    assert agg["partitions_read"] == 2
    assert agg["rows_read"] == 6  # rows really were read twice; the COUNT is what dedupes


def test_degree1_films_deduped_across_partitions(raw_dir: Path) -> None:
    """The one that would silently invert H1.

    A genuine one-credit actor whose single film spans two partitions must resolve to one
    distinct film, and therefore classify as `genuine`. If the dedupe breaks they look like
    they have two credits and get misfiled as `cap_induced`.
    """
    rows = [_row("Q1", "Q10"), _row("Q1", "Q11"), _row("Q1", "Q12")]
    _write_partition(1994, rows)
    _write_partition(1995, rows)

    agg = scan_raw(movie_qids={"Q1"}, actor_qids={"Q10"}, degree1_qids={"Q10"})
    assert agg["degree1_raw_films"]["Q10"] == {"Q1"}

    result = m2_genuine_vs_cap_induced({"Q10"}, agg)
    assert result["genuine"] == 1
    assert result["cap_induced"] == 0
    assert result["anomalous_count"] == 0


# --- the genuine / cap-induced split ----------------------------------------------


def test_actor_in_three_raw_films_but_degree_one_is_cap_induced(raw_dir: Path) -> None:
    """An actor the cast cap truncated out of every film but one is a build artifact, not
    a real one-credit performer, and must not be counted as legitimate obscure content."""
    _write_partition(
        2001,
        [
            _row("Q1", "Q10"),
            _row("Q2", "Q10"),
            _row("Q3", "Q10"),
            _row("Q1", "Q11"),
        ],
    )

    agg = scan_raw(movie_qids={"Q1", "Q2", "Q3"}, actor_qids={"Q10"}, degree1_qids={"Q10"})
    result = m2_genuine_vs_cap_induced({"Q10"}, agg)

    assert result["cap_induced"] == 1
    assert result["genuine"] == 0
    assert result["cap_induced_raw_film_count_histogram"] == {"3": 1}


def test_films_below_min_cast_are_excluded_from_the_population(raw_dir: Path) -> None:
    """Films the min_cast gate dropped are not graph nodes. Counting them would inflate an
    actor's apparent filmography and misfile genuine one-credit actors as cap-induced."""
    _write_partition(2001, [_row("Q1", "Q10"), _row("Q99", "Q10")])

    # Q99 never entered the graph, so it is absent from movie_qids.
    agg = scan_raw(movie_qids={"Q1"}, actor_qids={"Q10"}, degree1_qids={"Q10"})

    assert agg["degree1_raw_films"]["Q10"] == {"Q1"}
    assert m2_genuine_vs_cap_induced({"Q10"}, agg)["genuine"] == 1


# --- node classification ----------------------------------------------------------


def test_classification_ignores_entities_type() -> None:
    """entities[qid]["type"] is built last-write-wins, so a QID that is both film and cast
    member gets an arbitrary type (issue #19). Classification must key off the adjacency maps.
    """
    movies_to_actors = {"Q1": ["Q10", "Q11", "Q12"], "Q2": ["Q1", "Q13", "Q14"]}
    actors_to_movies = {
        "Q10": ["Q1"],
        "Q11": ["Q1"],
        "Q12": ["Q1"],
        "Q1": ["Q2"],
        "Q13": ["Q2"],
        "Q14": ["Q2"],
    }
    # Q1 is a film credited as cast in Q2, but entities mislabels it "actor".
    entities = {"Q1": {"label": "Jaws 2", "type": "actor"}}

    result = m5_both_map_qids(
        movie_qids=set(movies_to_actors),
        actor_qids=set(actors_to_movies),
        entities=entities,
        degree1_qids={"Q1", "Q10", "Q11", "Q12", "Q13", "Q14"},
        movies_to_actors=movies_to_actors,
        actors_to_movies=actors_to_movies,
    )

    assert result["count"] == 1
    assert result["qids"][0]["qid"] == "Q1"
    assert result["qids"][0]["assigned_type"] == "actor"  # recorded, not trusted
    assert result["qids"][0]["cast_size_as_movie"] == 3
    assert result["qids"][0]["degree_as_actor"] == 1


# --- decile bucketing -------------------------------------------------------------


def test_decile_buckets_deterministic_under_ties() -> None:
    """H4's verdict reads decile 9. With every film at the same sitelink count the split is
    entirely tiebreak-driven, so it must still be stable and equal-count."""
    items = [(f"Q{i}", 42) for i in range(1, 101)]

    first = decile_buckets(items)
    second = decile_buckets(list(reversed(items)))

    assert first == second
    assert [len(bucket) for bucket in first] == [10] * 10
    assert first[0][0] == "Q1"  # numeric QID ascending, not lexicographic
    assert first[9][-1] == "Q100"


def test_decile_buckets_orders_most_notable_last() -> None:
    items = [(f"Q{i}", i) for i in range(1, 101)]
    buckets = decile_buckets(items)

    assert buckets[0] == [f"Q{i}" for i in range(1, 11)]
    assert buckets[9] == [f"Q{i}" for i in range(91, 101)]


# --- invariant check --------------------------------------------------------------


def test_movie_degree_outside_cap_range_is_reported() -> None:
    """m1's free invariant: transform drops films below min_cast and _cap_cast truncates above
    cast_cap, so a movie degree outside that range means the artifact or this module is wrong."""
    movies_to_actors = {"Q1": ["Q10"], "Q2": ["Q11", "Q12", "Q13"]}
    actors_to_movies = {"Q10": ["Q1"], "Q11": ["Q2"], "Q12": ["Q2"], "Q13": ["Q2"]}

    _, violations = m1_degree_distribution(
        actors_to_movies, movies_to_actors, min_cast=3, cast_cap=15
    )

    assert len(violations) == 1
    assert "min_cast=3" in violations[0]
