"""Stage 3 — emit: build_adjacency, build_entities, and the full artifact write."""

import json

from _harness import make_edge, require


def test_adjacency_is_symmetric():
    build_adjacency = require("emit", "build_adjacency")
    edges = [make_edge("Q1", "Q10"), make_edge("Q1", "Q11"), make_edge("Q2", "Q10")]
    movie_to_actors, actor_to_movies = build_adjacency(edges)
    for movie, actors in movie_to_actors.items():
        for actor in actors:
            assert movie in actor_to_movies[actor], f"{movie}->{actor} has no inverse"
    for actor, movies in actor_to_movies.items():
        for movie in movies:
            assert actor in movie_to_actors[movie], f"{actor}->{movie} has no inverse"
    assert actor_to_movies["Q10"] == {"Q1", "Q2"}, "Q10 acted in both films"


def test_entities_are_typed_and_deduped():
    build_entities = require("emit", "build_entities")
    entities = build_entities([make_edge("Q1", "Q10"), make_edge("Q1", "Q10")])
    assert entities["Q1"]["type"] == "movie"
    assert entities["Q10"]["type"] == "actor"
    assert entities["Q1"]["label"] == "label-Q1"


def _run_emit(tmp_path, monkeypatch, edges):
    """Redirect the output/provenance dirs into tmp and run emit()."""
    emit = require("emit")
    paths = require("paths")
    BuildConfig = require("config", "BuildConfig")
    monkeypatch.setattr(paths, "GRAPH_DIR", tmp_path / "graph", raising=False)
    monkeypatch.setattr(paths, "RAW_DIR", tmp_path / "raw", raising=False)
    (tmp_path / "raw").mkdir(parents=True, exist_ok=True)
    emit.emit(edges, BuildConfig(), "v1")
    out = tmp_path / "graph" / "v1"
    graph = json.loads((out / "graph.json").read_text())
    manifest = json.loads((out / "manifest.json").read_text())
    return graph, manifest


def test_artifact_shape_keys_are_qids_and_lists_are_sorted(tmp_path, monkeypatch):
    # actors inserted out of order so an unsorted serialization is caught
    edges = [make_edge("Q1", "Q30"), make_edge("Q1", "Q10"), make_edge("Q1", "Q20")]
    graph, manifest = _run_emit(tmp_path, monkeypatch, edges)

    assert set(graph) >= {"movies", "actors"}, "graph.json needs 'movies' and 'actors' maps"
    assert all(k.startswith("Q") for k in graph["movies"]), (
        "keys must stay Wikidata QIDs (strings) — don't map to ints here (that's the loader's job)."
    )
    actors = graph["movies"]["Q1"]
    assert actors == sorted(actors), (
        "serialize each adjacency set as a SORTED list — otherwise output isn't reproducible "
        "across runs (Python randomizes set iteration order between processes)."
    )


def test_manifest_records_config_and_counts(tmp_path, monkeypatch):
    edges = [make_edge("Q1", "Q10"), make_edge("Q1", "Q11"), make_edge("Q2", "Q10")]
    graph, manifest = _run_emit(tmp_path, monkeypatch, edges)
    assert manifest["counts"]["n_movies"] == 2      # {Q1, Q2}
    assert manifest["counts"]["n_actors"] == 2       # {Q10, Q11} — Q10 bridges both films
    assert manifest["counts"]["n_edges"] == 3
    assert manifest["config"]["cast_cap"] == 15, "the gameplay dials must travel with the data"
    assert manifest["source"] == "wikidata"


def test_emit_is_reproducible_across_runs(tmp_path, monkeypatch):
    edges = [make_edge("Q1", "Q30"), make_edge("Q1", "Q10"), make_edge("Q2", "Q10")]
    out = tmp_path / "graph" / "v1" / "graph.json"
    _run_emit(tmp_path, monkeypatch, edges)
    first = out.read_bytes()
    _run_emit(tmp_path, monkeypatch, edges)  # overwrite same version
    assert out.read_bytes() == first, "re-running emit on the same edges must be byte-identical"
