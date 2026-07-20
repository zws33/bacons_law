"""Tests for the WDQS client (etl.sparql) — all network-free.

Two seams are worth covering here:
  * _flatten / _qid_from_uri — the pure payload -> rows mapping;
  * query() error handling — HTTP + non-JSON failures map to SparqlError,
    and the happy path returns flattened rows and sends a User-Agent.

httpx2.post is monkeypatched throughout; nothing hits the real endpoint.
"""

import httpx2
import pytest

from etl.config import BuildConfig
from etl.sparql import (
    SparqlError,
    _flatten,
    _qid_from_uri,
    _Row,
    _SparqlResponse,
    query,
)


def _binding(film: str, actor: str, film_links: int, actor_links: int) -> _Row:
    """One SPARQL result binding in WDQS JSON shape."""
    return {
        "film": {"type": "uri", "value": f"http://www.wikidata.org/entity/{film}"},
        "filmLabel": {"type": "literal", "value": f"label-{film}"},
        "filmSitelinks": {"type": "literal", "value": str(film_links)},
        "actor": {"type": "uri", "value": f"http://www.wikidata.org/entity/{actor}"},
        "actorLabel": {"type": "literal", "value": f"label-{actor}"},
        "actorSitelinks": {"type": "literal", "value": str(actor_links)},
    }


def _payload(*bindings: _Row) -> _SparqlResponse:
    return {"results": {"bindings": list(bindings)}}


class _FakeResponse:
    """Stand-in for an httpx2 response.

    raise_exc / json_exc let a test force failures at raise_for_status() or
    json() to exercise query()'s except branches.
    """

    def __init__(self, json_body=None, *, raise_exc=None, json_exc=None):
        self._json_body = json_body
        self._raise_exc = raise_exc
        self._json_exc = json_exc

    def raise_for_status(self):
        if self._raise_exc is not None:
            raise self._raise_exc
        return self

    def json(self):
        if self._json_exc is not None:
            raise self._json_exc
        return self._json_body


# --- pure mapping -----------------------------------------------------------


def test_qid_from_uri_extracts_last_segment():
    assert _qid_from_uri("http://www.wikidata.org/entity/Q11424") == "Q11424"


def test_flatten_maps_all_six_fields():
    rows = _flatten(_payload(_binding("Q1", "Q10", film_links=100, actor_links=50)))
    assert rows == [
        {
            "film": "Q1",
            "film_label": "label-Q1",
            "film_sitelinks": 100,
            "actor": "Q10",
            "actor_label": "label-Q10",
            "actor_sitelinks": 50,
        }
    ]


def test_flatten_coerces_sitelinks_to_int():
    # WDQS sends counts as JSON strings; _flatten must return real ints.
    rows = _flatten(_payload(_binding("Q1", "Q10", film_links=7, actor_links=3)))
    assert isinstance(rows[0]["film_sitelinks"], int)
    assert isinstance(rows[0]["actor_sitelinks"], int)


def test_flatten_empty_bindings_yields_no_rows():
    assert _flatten(_payload()) == []


def test_flatten_preserves_row_order():
    rows = _flatten(
        _payload(
            _binding("Q1", "Q10", 100, 50),
            _binding("Q2", "Q20", 90, 40),
        )
    )
    assert [r["film"] for r in rows] == ["Q1", "Q2"]


# --- query(): happy path ----------------------------------------------------


def test_query_returns_flattened_rows(monkeypatch):
    monkeypatch.setattr(
        httpx2,
        "post",
        lambda **kw: _FakeResponse(_payload(_binding("Q1", "Q10", 100, 50))),
    )
    rows = query("SELECT ...", BuildConfig())
    assert rows[0]["film"] == "Q1"
    assert rows[0]["actor_sitelinks"] == 50


def test_query_sends_required_user_agent(monkeypatch):
    # A generic/absent User-Agent is blocked by WDQS — assert we send ours.
    captured: dict = {}

    def fake_post(**kw):
        captured.update(kw)
        return _FakeResponse(_payload())

    monkeypatch.setattr(httpx2, "post", fake_post)
    cfg = BuildConfig()
    _ = query("SELECT ...", cfg)
    assert captured["headers"]["User-Agent"] == cfg.user_agent
    assert captured["data"] == {"query": "SELECT ..."}


# --- query(): failure mapping ----------------------------------------------


def test_query_wraps_http_error(monkeypatch):
    monkeypatch.setattr(
        httpx2,
        "post",
        lambda **kw: _FakeResponse(raise_exc=httpx2.HTTPError("503 boom")),
    )
    with pytest.raises(SparqlError, match="WDQS request failed"):
        query("SELECT ...", BuildConfig())


def test_query_wraps_non_json_body(monkeypatch):
    # A timeout/error page comes back as HTML -> response.json() raises ValueError.
    monkeypatch.setattr(
        httpx2,
        "post",
        lambda **kw: _FakeResponse(json_exc=ValueError("no JSON")),
    )
    with pytest.raises(SparqlError, match="non-JSON body"):
        query("SELECT ...", BuildConfig())


def test_query_wraps_malformed_shape_missing_key(monkeypatch):
    # A binding missing a required variable -> KeyError in _flatten -> SparqlError.
    bad = {"results": {"bindings": [{"film": {"value": "http://www.wikidata.org/entity/Q1"}}]}}
    monkeypatch.setattr(httpx2, "post", lambda **kw: _FakeResponse(bad))
    with pytest.raises(SparqlError, match="unexpected WDQS response shape"):
        query("SELECT ...", BuildConfig())


def test_query_wraps_non_numeric_sitelinks(monkeypatch):
    # A sitelinks count that isn't an int -> ValueError in _flatten -> SparqlError,
    # and it must NOT be mislabeled as a non-JSON body (the body parsed fine).
    binding = _binding("Q1", "Q10", 100, 50)
    binding["filmSitelinks"] = {"type": "literal", "value": "not-a-number"}
    monkeypatch.setattr(httpx2, "post", lambda **kw: _FakeResponse(_payload(binding)))
    with pytest.raises(SparqlError, match="unexpected WDQS response shape"):
        query("SELECT ...", BuildConfig())


def test_query_error_chains_original_cause(monkeypatch):
    boom = httpx2.HTTPError("503 boom")
    monkeypatch.setattr(httpx2, "post", lambda **kw: _FakeResponse(raise_exc=boom))
    with pytest.raises(SparqlError) as exc:
        query("SELECT ...", BuildConfig())
    assert exc.value.__cause__ is boom


def test_sparql_error_has_default_message():
    assert str(SparqlError()) == SparqlError.default_message
