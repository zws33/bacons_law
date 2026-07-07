"""Stage 1 — extract: sparql.py (client + parser) and extract.py (fetch loop).

Offline by default. The one real-network test is marked `live` and only runs
with `--run-live`.
"""

import pytest

from _harness import SPARQL_PAYLOAD, FakeResponse, require

# --- sparql.py: URL/QID + type parsing ------------------------------------- #

def test_qid_from_uri_strips_the_prefix():
    qid_from_uri = require("sparql", "qid_from_uri")
    assert qid_from_uri("http://www.wikidata.org/entity/Q25188") == "Q25188", (
        "Return only the final path segment (the QID), not the whole URL."
    )


def test_query_parses_uris_to_qids_and_counts_to_ints(monkeypatch):
    """query() should return flat rows: bare QIDs and integer sitelink counts."""
    sparql = require("sparql")
    query = require("sparql", "query")
    BuildConfig = require("config", "BuildConfig")

    # Works whether you wrote `import httpx2 as httpx` or `import httpx2`.
    http = getattr(sparql, "httpx", None) or getattr(sparql, "httpx2", None)
    if http is None:
        pytest.skip("This test assumes sparql.py imports httpx2 (as httpx, or as httpx2).")
    # Intercept whichever verb you used (GET or POST) — no network happens.
    fake = lambda *a, **k: FakeResponse(SPARQL_PAYLOAD)  # noqa: E731
    monkeypatch.setattr(http, "post", fake, raising=False)
    monkeypatch.setattr(http, "get", fake, raising=False)

    rows = query("SELECT ...", BuildConfig())
    assert len(rows) == 2
    first = rows[0]
    assert first["film"] == "Q25188", "did you strip the entity URI to a QID?"
    assert first["actor"] == "Q38111"
    assert isinstance(first["film_sitelinks"], int), (
        "sitelink counts arrive as strings — wrap the value in int()."
    )
    assert isinstance(first["actor_sitelinks"], int)


# --- extract.py: query templating ------------------------------------------ #

def test_render_query_is_fully_templated_from_config():
    render_query = require("extract", "render_query")
    BuildConfig = require("config", "BuildConfig")

    q = render_query(1994, BuildConfig(min_sitelinks=7))
    assert "YEAR(?date) = 1994" in q, "the year filter must use the argument, not a hardcoded year"
    assert ">= 7" in q, "the sitelink floor must come from config, not a hardcoded 5"
    assert "en.wikipedia.org" in q, "require_enwiki=True should add the enwiki anchor"

    q2 = render_query(1994, BuildConfig(require_enwiki=False))
    assert "en.wikipedia.org" not in q2, "require_enwiki=False should drop the enwiki anchor"


# --- extract.py: the cache-validity behaviour (decision D1) ---------------- #

def test_cache_skips_on_match_and_refetches_on_param_change(monkeypatch, tmp_path):
    """A cached year is reused only while min_sitelinks/require_enwiki still match."""
    extract = require("extract")
    sparql = require("sparql")
    paths = require("paths")
    BuildConfig = require("config", "BuildConfig")

    monkeypatch.setattr(paths, "RAW_DIR", tmp_path, raising=False)

    calls = {"n": 0}

    def fake_query(text, config):
        calls["n"] += 1
        return [
            {
                "film": "Q1", "film_label": "F", "film_sitelinks": 9,
                "actor": "Q10", "actor_label": "A", "actor_sitelinks": 5,
            }
        ]

    monkeypatch.setattr(sparql, "query", fake_query)

    cfg = BuildConfig(from_year=2000, to_year=2000)
    extract.extract(cfg)
    assert calls["n"] == 1, "first run should fetch the year"

    extract.extract(cfg)
    assert calls["n"] == 1, (
        "second run with identical params should SKIP the cached year, not refetch. "
        "Does your skip check that the cache exists?"
    )

    extract.extract(BuildConfig(from_year=2000, to_year=2000, min_sitelinks=99))
    assert calls["n"] == 2, (
        "changing min_sitelinks must invalidate the cache and refetch (decision D1). "
        "Record min_sitelinks/require_enwiki in each raw file and compare them before skipping."
    )


# --- the opt-in live smoke test -------------------------------------------- #

@pytest.mark.live
def test_live_smoke_one_year():
    """Real WDQS call for one year. Run with:  uv run pytest --run-live"""
    sparql = require("sparql")
    render_query = require("extract", "render_query")
    BuildConfig = require("config", "BuildConfig")
    rows = sparql.query(render_query(1994, BuildConfig()), BuildConfig())
    assert rows, "expected some rows for 1994"
    assert rows[0]["film"].startswith("Q")
    assert isinstance(rows[0]["actor_sitelinks"], int)
