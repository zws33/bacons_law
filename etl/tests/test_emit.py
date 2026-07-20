"""Tests for the emit stage (etl.emit) — network-free, disk confined to tmp_path.

Five seams:
  * _load_edges       — the inverse of transform's asdict() write; Edge is a plain
                        dataclass, so a renamed/missing field must surface as a
                        ValueError naming the file, not a bare TypeError;
  * _build_adjacency  — the symmetry invariant: the reverse map is DERIVED from the
                        forward one, so an asymmetric graph is structurally impossible;
  * _build_entities   — the typeahead index: qid -> {label, type}, covering every node;
  * _query_date_range — provenance span across the raw cache, tolerant of junk files;
  * emit()            — the artifact: both files written, manifest self-describing,
                        and byte-identical across re-runs (the reproducibility claim).

paths.* are redirected to tmp dirs, so nothing touches the real data/ or graph/ tree.
"""

import dataclasses
import json
from pathlib import Path

import pytest

from etl import emit, paths, transform
from etl.config import BuildConfig
from etl.models import Edge

# --- fixtures / helpers -----------------------------------------------------------


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the raw / interim / graph trees into tmp_path.

    emit and transform both reach paths.* through the module (not a from-import), so
    patching the module attributes is enough: edges_path() and graph_version_dir()
    read the globals at call time.
    """
    raw = tmp_path / "raw"
    interim = tmp_path / "interim"
    raw.mkdir()
    interim.mkdir()
    monkeypatch.setattr(paths, "RAW_DIR", raw)
    monkeypatch.setattr(paths, "INTERIM_DIR", interim)
    monkeypatch.setattr(paths, "GRAPH_DIR", tmp_path / "graph")
    return tmp_path


def _edge(movie: str = "Q1", actor: str = "Q10") -> Edge:
    return Edge(
        movie=movie,
        movie_label=f"Film {movie}",
        actor=actor,
        actor_label=f"Actor {actor}",
    )


def _write_edges(edges: list[Edge]) -> None:
    """Write edges.jsonl the way transform actually writes it (not a hand-rolled copy),
    so these tests break if the two stages ever disagree on the format."""
    transform._write_edges(edges)


def _write_raw(path: Path, fetched_at: str) -> None:
    path.write_text(json.dumps({"fetched_at": fetched_at}))


# --- _load_edges ------------------------------------------------------------------


def test_load_edges_round_trips_transform_output(tree: Path):
    """emit reads back exactly what transform wrote — the interim-file contract."""
    edges = [_edge("Q1", "Q10"), _edge("Q2", "Q20")]
    _write_edges(edges)
    assert emit._load_edges() == edges


def test_load_edges_empty_file_yields_no_edges(tree: Path):
    _write_edges([])
    assert emit._load_edges() == []


def test_load_edges_unknown_field_raises_value_error_naming_the_file(tree: Path):
    """Schema drift is the realistic failure here, and Edge(**r) catches it by NAME.
    The message must name the file — a bare TypeError gives no clue where to look."""
    paths.edges_path().write_text(json.dumps({"movie": "Q1", "surprise": "x"}))
    with pytest.raises(ValueError, match="Failed to load edges from"):
        emit._load_edges()


def test_load_edges_missing_field_raises_value_error(tree: Path):
    paths.edges_path().write_text(json.dumps({"movie": "Q1", "actor": "Q10"}))
    with pytest.raises(ValueError, match="Failed to load edges from"):
        emit._load_edges()


# --- _build_adjacency -------------------------------------------------------------


def test_build_adjacency_maps_movie_to_its_cast():
    movies, _ = emit._build_adjacency([_edge("Q1", "Q10"), _edge("Q1", "Q11")])
    assert movies == {"Q1": {"Q10", "Q11"}}


def test_build_adjacency_inverts_to_actor_to_movies():
    _, actors = emit._build_adjacency([_edge("Q1", "Q10"), _edge("Q2", "Q10")])
    assert actors == {"Q10": {"Q1", "Q2"}}


def test_build_adjacency_is_symmetric():
    """The one invariant a graph bug would violate. Checked in both directions."""
    edges = [
        _edge("Q1", "Q10"),
        _edge("Q1", "Q11"),
        _edge("Q2", "Q10"),
        _edge("Q3", "Q12"),
    ]
    movies, actors = emit._build_adjacency(edges)
    for movie, cast in movies.items():
        for actor in cast:
            assert movie in actors[actor]
    for actor, filmography in actors.items():
        for movie in filmography:
            assert actor in movies[movie]


def test_build_adjacency_dedupes_repeated_edges():
    movies, actors = emit._build_adjacency([_edge("Q1", "Q10"), _edge("Q1", "Q10")])
    assert movies == {"Q1": {"Q10"}}
    assert actors == {"Q10": {"Q1"}}


def test_build_adjacency_empty_edges():
    movies, actors = emit._build_adjacency([])
    assert dict(movies) == {}
    assert dict(actors) == {}


# --- _build_entities --------------------------------------------------------------


def test_build_entities_labels_and_types_both_sides():
    entities = emit._build_entities([_edge("Q1", "Q10")])
    assert entities == {
        "Q1": {"label": "Film Q1", "type": "movie"},
        "Q10": {"label": "Actor Q10", "type": "actor"},
    }


def test_build_entities_covers_every_node():
    edges = [_edge("Q1", "Q10"), _edge("Q1", "Q11"), _edge("Q2", "Q10")]
    movies, actors = emit._build_adjacency(edges)
    entities = emit._build_entities(edges)
    assert set(entities) == set(movies) | set(actors)


# --- _sorted_adjacency ------------------------------------------------------------


def test_sorted_adjacency_sorts_values():
    """Sets have no order; sorting on write is what makes the artifact reproducible."""
    assert emit._sorted_adjacency({"Q1": {"Q30", "Q10", "Q20"}}) == {
        "Q1": ["Q10", "Q20", "Q30"]
    }


# --- _query_date_range ------------------------------------------------------------


def test_query_date_range_spans_min_and_max(tree: Path):
    _write_raw(paths.RAW_DIR / "films-1997.json", "2026-07-18T00:00:00+00:00")
    _write_raw(paths.RAW_DIR / "films-2010.json", "2026-07-19T00:00:00+00:00")
    _write_raw(paths.RAW_DIR / "films-2001.json", "2026-07-20T00:00:00+00:00")
    assert emit._query_date_range() == {
        "from": "2026-07-18T00:00:00+00:00",
        "to": "2026-07-20T00:00:00+00:00",
    }


def test_query_date_range_empty_cache_is_null_span(tree: Path):
    assert emit._query_date_range() == {"from": None, "to": None}


def test_query_date_range_skips_corrupt_and_stale_files(tree: Path):
    """A half-written or old-format (bare list) cache file must not crash provenance."""
    (paths.RAW_DIR / "films-1994.json").write_text("{ half-written")
    (paths.RAW_DIR / "films-1995.json").write_text(json.dumps([{"film": "Q1"}]))
    _write_raw(paths.RAW_DIR / "films-1996.json", "2026-07-18T00:00:00+00:00")
    assert emit._query_date_range() == {
        "from": "2026-07-18T00:00:00+00:00",
        "to": "2026-07-18T00:00:00+00:00",
    }


# --- emit() -----------------------------------------------------------------------


def test_emit_raises_when_no_edges(tree: Path):
    """Emitting an empty graph is always a pipeline bug, never a valid build."""
    _write_edges([])
    with pytest.raises(ValueError, match="no edges"):
        emit.emit(BuildConfig(), "v1")


def test_emit_writes_both_artifact_files(tree: Path):
    _write_edges([_edge("Q1", "Q10")])
    out = emit.emit(BuildConfig(), "v1")
    assert out == paths.graph_version_dir("v1")
    assert (out / "graph.json").exists()
    assert (out / "manifest.json").exists()


def test_emit_graph_has_all_three_maps(tree: Path):
    _write_edges([_edge("Q1", "Q10"), _edge("Q2", "Q10")])
    out = emit.emit(BuildConfig(), "v1")
    graph = json.loads((out / "graph.json").read_text())
    assert graph["movies_to_actors"] == {"Q1": ["Q10"], "Q2": ["Q10"]}
    assert graph["actors_to_movies"] == {"Q10": ["Q1", "Q2"]}
    assert graph["entities"]["Q10"] == {"label": "Actor Q10", "type": "actor"}


def test_emit_manifest_records_config_and_counts(tree: Path):
    """The dials must travel WITH the data — a build is reproducible only if it says
    what went into it."""
    _write_edges([_edge("Q1", "Q10"), _edge("Q1", "Q11"), _edge("Q2", "Q11")])
    cfg = BuildConfig(min_sitelinks=7, min_cast=4, cast_cap=9, require_enwiki=False)
    out = emit.emit(cfg, "v2")

    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["schema_version"] == emit.SCHEMA_VERSION
    assert manifest["version"] == "v2"
    assert manifest["source"] == "wikidata"
    assert manifest["config"] == {
        "min_sitelinks": 7,
        "min_cast": 4,
        "cast_cap": 9,
        "require_enwiki": False,
        "year_from": cfg.year_from,
        "year_to": cfg.year_to,
    }
    assert manifest["counts"] == {"n_movies": 2, "n_actors": 2, "n_edges": 3}


def test_emit_manifest_carries_query_date_from_raw_cache(tree: Path):
    _write_raw(paths.RAW_DIR / "films-1994.json", "2026-07-18T00:00:00+00:00")
    _write_edges([_edge("Q1", "Q10")])
    out = emit.emit(BuildConfig(), "v1")
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["query_date"]["from"] == "2026-07-18T00:00:00+00:00"


def test_emit_version_selects_the_output_directory(tree: Path):
    """A re-tuned build is a new version beside the old one, not an in-place mutation."""
    _write_edges([_edge("Q1", "Q10")])
    emit.emit(BuildConfig(cast_cap=5), "v1")
    emit.emit(BuildConfig(cast_cap=9), "v2")

    v1 = json.loads((paths.graph_version_dir("v1") / "manifest.json").read_text())
    v2 = json.loads((paths.graph_version_dir("v2") / "manifest.json").read_text())
    assert v1["config"]["cast_cap"] == 5
    assert v2["config"]["cast_cap"] == 9


def test_emit_is_byte_reproducible(tree: Path):
    """Same input -> byte-identical graph.json. Guards the diffability claim; the
    manifest is excluded because generated_at is a timestamp by design."""
    _write_edges([_edge("Q2", "Q20"), _edge("Q1", "Q11"), _edge("Q1", "Q10")])
    out = emit.emit(BuildConfig(), "v1")
    first = (out / "graph.json").read_bytes()
    emit.emit(BuildConfig(), "v1")
    assert (out / "graph.json").read_bytes() == first


def test_emit_output_is_insensitive_to_edge_order(tree: Path):
    """Reordering the interim file must not change the artifact — otherwise 'same input,
    same graph' depends on transform's iteration order rather than on the data."""
    edges = [_edge("Q1", "Q10"), _edge("Q1", "Q11"), _edge("Q2", "Q20")]

    _write_edges(edges)
    forward = (emit.emit(BuildConfig(), "v1") / "graph.json").read_bytes()

    _write_edges(list(reversed(edges)))
    reversed_ = (emit.emit(BuildConfig(), "v1") / "graph.json").read_bytes()

    assert forward == reversed_


def test_emit_graph_json_round_trips_to_the_same_edge_set(tree: Path):
    """End of the stage: the artifact must describe exactly the edges it was built from."""
    edges = [_edge("Q1", "Q10"), _edge("Q1", "Q11"), _edge("Q2", "Q10")]
    _write_edges(edges)
    out = emit.emit(BuildConfig(), "v1")

    graph = json.loads((out / "graph.json").read_text())
    rebuilt = {
        (movie, actor)
        for movie, cast in graph["movies_to_actors"].items()
        for actor in cast
    }
    assert rebuilt == {(e.movie, e.actor) for e in edges}


def test_emit_survives_a_truncated_previous_artifact(tree: Path):
    """write_atomic means a half-written graph.json from a killed run is replaced
    wholesale, never merged into."""
    out_dir = paths.graph_version_dir("v1")
    out_dir.mkdir(parents=True)
    (out_dir / "graph.json").write_text('{"movies_to_actors": {"Q9')

    _write_edges([_edge("Q1", "Q10")])
    out = emit.emit(BuildConfig(), "v1")
    graph = json.loads((out / "graph.json").read_text())
    assert graph["movies_to_actors"] == {"Q1": ["Q10"]}


def test_edge_dataclass_field_names_match_the_written_json(tree: Path):
    """Guards the seam we deliberately left unvalidated at runtime: if Edge's fields are
    renamed, transform's asdict() keys and emit's Edge(**r) drift apart silently."""
    _write_edges([_edge("Q1", "Q10")])
    written = json.loads(paths.edges_path().read_text())
    assert set(written) == {f.name for f in dataclasses.fields(Edge)}
