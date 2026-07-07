"""Stage 0 — the shared contracts: config.py, models.py, paths.py.

These have no dependencies, so build them first. Everything else imports them.
"""

import dataclasses

import pytest

from _harness import require

# --- config.py ------------------------------------------------------------- #

def test_buildconfig_has_the_expected_defaults():
    BuildConfig = require("config", "BuildConfig")
    c = BuildConfig()
    assert c.min_sitelinks == 5
    assert c.min_cast == 3
    assert c.cast_cap == 15
    assert c.require_enwiki is True
    assert c.from_year == 1900
    assert c.to_year == 2026
    assert "@" in c.user_agent, "user_agent must include contact info (WDQS requires it)"
    assert c.endpoint.startswith("https://"), "endpoint should be the WDQS https URL"


def test_buildconfig_is_frozen():
    BuildConfig = require("config", "BuildConfig")
    c = BuildConfig()
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.cast_cap = 99  # frozen=True makes config immutable — a build param can't drift mid-run


# --- models.py ------------------------------------------------------------- #

def test_models_construct_with_the_expected_fields():
    Actor, Film, Edge = require("models", "Actor", "Film", "Edge")
    a = Actor("Q10", "Ada", 42)
    assert (a.qid, a.label, a.sitelinks) == ("Q10", "Ada", 42)
    f = Film("Q1", "Film", 100)
    assert (f.qid, f.label, f.sitelinks) == ("Q1", "Film", 100)
    assert f.cast == {}, "a fresh Film should start with an empty cast dict"
    e = Edge("Q1", "Film", "Q10", "Ada")
    assert (e.movie, e.movie_label, e.actor, e.actor_label) == ("Q1", "Film", "Q10", "Ada")


def test_film_cast_is_not_a_shared_default():
    """The classic Python gotcha: a mutable default shared across instances.

    In a dataclass you must write `cast: dict = field(default_factory=dict)`,
    NOT `cast: dict = {}`. If this fails, every Film is sharing one dict.
    """
    Film = require("models", "Film")
    a, b = Film("Q1", "A", 1), Film("Q2", "B", 2)
    a.cast["Q10"] = "x"
    assert "Q10" not in b.cast, (
        "Two Film objects share the same cast dict — use "
        "field(default_factory=dict), not a bare = {} default."
    )


# --- paths.py -------------------------------------------------------------- #

def test_paths_resolve_relative_to_the_etl_root():
    paths = require("paths")
    assert paths.ROOT.name == "etl", (
        f"paths.ROOT should be the etl/ project dir, got {paths.ROOT}. "
        "Check your parents[...] index — paths.py lives at src/etl/paths.py."
    )
    assert paths.raw_path(1994).name == "films-1994.json"
    assert paths.edges_path().name == "edges.jsonl"
    assert paths.graph_version_dir("v1").name == "v1"
    # raw files live under data/raw, the artifact under graph/
    assert paths.raw_path(1994).parent == paths.RAW_DIR
    assert paths.graph_version_dir("v1").parent == paths.GRAPH_DIR
