"""Stage 4 — the whole pipeline wired together, plus the CLI arg→config mapping.

The end-to-end test fakes the SPARQL call (no network) and runs
extract → transform → emit into a temp tree, then checks the artifact is correct
and reproducible. It stays SKIPPED until every stage is built.
"""

import json
import types

from _harness import PIPELINE_ROWS, require


def test_config_from_args_maps_flags_to_fields():
    """--year-from → from_year, --cap → cast_cap; unset flags keep defaults."""
    _config_from_args = require("__main__", "_config_from_args")
    args = types.SimpleNamespace(
        year_from=1995, year_to=None, cap=10, min_sitelinks=None, min_cast=None
    )
    cfg = _config_from_args(args)
    assert cfg.from_year == 1995
    assert cfg.cast_cap == 10
    assert cfg.to_year == 2026, "unset flags must fall back to the BuildConfig default"
    assert cfg.min_sitelinks == 5


def test_full_pipeline_builds_a_correct_reproducible_artifact(tmp_path, monkeypatch):
    extract = require("extract")
    transform = require("transform")
    emit = require("emit")
    sparql = require("sparql")
    paths = require("paths")
    BuildConfig = require("config", "BuildConfig")

    # Redirect every on-disk location into tmp so we never touch real data/.
    monkeypatch.setattr(paths, "RAW_DIR", tmp_path / "raw", raising=False)
    monkeypatch.setattr(paths, "INTERIM_DIR", tmp_path / "interim", raising=False)
    monkeypatch.setattr(paths, "GRAPH_DIR", tmp_path / "graph", raising=False)

    # Fake the network: any query returns our canned chain.
    monkeypatch.setattr(sparql, "query", lambda text, config: list(PIPELINE_ROWS))

    cfg = BuildConfig(from_year=2000, to_year=2000)  # one fake fetch
    extract.extract(cfg)
    edges = transform.transform(cfg)
    emit.emit(edges, cfg, "v1")

    graph_path = tmp_path / "graph" / "v1" / "graph.json"
    manifest_path = tmp_path / "graph" / "v1" / "manifest.json"
    assert graph_path.exists(), "emit must write graph.json"
    assert manifest_path.exists(), "emit must write manifest.json"

    graph = json.loads(graph_path.read_text())
    manifest = json.loads(manifest_path.read_text())

    # The chain: Q10 bridges Q1 and Q2.
    assert graph["actors"]["Q10"] == ["Q1", "Q2"]
    assert "Q10" in graph["movies"]["Q1"] and "Q10" in graph["movies"]["Q2"]

    # Symmetry across the whole graph.
    for movie, actors in graph["movies"].items():
        for actor in actors:
            assert movie in graph["actors"][actor]

    assert manifest["counts"] == {"n_movies": 2, "n_actors": 5, "n_edges": 6}

    # Reproducibility: rebuilding is byte-identical.
    first = graph_path.read_bytes()
    emit.emit(edges, cfg, "v1")
    assert graph_path.read_bytes() == first, "a rebuild on the same inputs must be byte-identical"


def test_rerun_uses_the_cache_and_makes_no_new_calls(tmp_path, monkeypatch):
    extract = require("extract")
    sparql = require("sparql")
    paths = require("paths")
    BuildConfig = require("config", "BuildConfig")

    monkeypatch.setattr(paths, "RAW_DIR", tmp_path / "raw", raising=False)
    calls = {"n": 0}

    def fake_query(text, config):
        calls["n"] += 1
        return list(PIPELINE_ROWS)

    monkeypatch.setattr(sparql, "query", fake_query)

    cfg = BuildConfig(from_year=2000, to_year=2001)  # two years → two fetches, once
    extract.extract(cfg)
    extract.extract(cfg)
    assert calls["n"] == 2, "the second full run should hit the cache and make zero new calls"
