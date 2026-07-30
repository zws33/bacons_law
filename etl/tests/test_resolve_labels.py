"""Tests for the resolve stage (etl.resolve_labels) — network-free.

Seams:
  * resolve_labels() happy path — fetch en labels, misses stored as null;
  * 429 handling — a rate-limited batch is retried, not dropped;
  * resume — attempted QIDs (resolved AND null-miss) are not refetched, so a
    genuine miss isn't queried forever;
  * checkpointing — a mid-run checkpoint contains ATTEMPTED-ONLY QIDs (the §2.2
    trap: seeding every missing QID up front would poison presence-based resume).

httpx2.get is monkeypatched throughout; paths.* are redirected to tmp dirs, so
nothing hits the network or the real data/ tree.
"""

import json
import time
from pathlib import Path

import httpx2
import pytest

from etl import paths, resolve_labels, transform
from etl.config import BuildConfig
from etl.models import Edge


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the interim (edges) and data (labels) trees into tmp_path.

    resolve reaches paths.* through the module, so edges_path() and labels_path()
    read the patched globals at call time.
    """
    interim = tmp_path / "interim"
    data = tmp_path / "data"
    interim.mkdir()
    data.mkdir()
    monkeypatch.setattr(paths, "INTERIM_DIR", interim)
    monkeypatch.setattr(paths, "DATA_DIR", data)
    return tmp_path


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never actually sleep on a 429 backoff during tests."""
    monkeypatch.setattr(time, "sleep", lambda _: None)


def _write_edges(edges: list[Edge]) -> None:
    """Write edges.jsonl the way transform actually writes it, so these tests break
    if the two stages ever disagree on the format."""
    transform._write_edges(edges)


class _FakeResponse:
    """Stand-in for an httpx2 response covering what resolve touches."""

    def __init__(self, body: dict, *, status_code: int = 200, headers: dict | None = None):
        self._body = body
        self.status_code = status_code
        self.headers = headers or {}

    def raise_for_status(self):
        return self

    def json(self):
        return self._body


def _entity(qid: str, label: str | None) -> dict:
    """One wbgetentities entity; an absent en label (a miss) is an empty labels dict."""
    labels = {} if label is None else {"en": {"language": "en", "value": label}}
    return {"type": "item", "id": qid, "labels": labels}


def _wb_body(label_map: dict[str, str], ids: list[str]) -> dict:
    """A wbgetentities response for the requested ids; label_map.get(qid) is the name,
    or None (miss) for QIDs not in the map."""
    return {"entities": {q: _entity(q, label_map.get(q)) for q in ids}}


def _fake_get(label_map: dict[str, str], calls: list[list[str]]):
    """A stub for httpx2.get that serves labels from label_map and records each
    requested id-batch in `calls`."""

    def get(url, *, params, headers, timeout):
        ids = params["ids"].split("|")
        calls.append(ids)
        return _FakeResponse(_wb_body(label_map, ids))

    return get


# --- happy path -------------------------------------------------------------


def test_resolve_fetches_and_writes_labels(tree: Path, monkeypatch: pytest.MonkeyPatch):
    _write_edges([Edge("Q1", "Q10"), Edge("Q2", "Q20")])
    label_map = {"Q1": "Film One", "Q10": "Actor Ten", "Q2": "Film Two"}  # Q20 -> miss
    calls: list[list[str]] = []
    monkeypatch.setattr(httpx2, "get", _fake_get(label_map, calls))

    stats = resolve_labels.resolve_labels(BuildConfig())

    written = json.loads(paths.labels_path().read_text())
    assert written == {"Q1": "Film One", "Q10": "Actor Ten", "Q2": "Film Two", "Q20": None}
    assert stats.n_labels == 3  # nulls are not counted as resolved labels


def test_resolve_writes_sorted_keys(tree: Path, monkeypatch: pytest.MonkeyPatch):
    # byte-reproducibility: keys are sorted on write regardless of fetch order.
    _write_edges([Edge("Q2", "Q30"), Edge("Q1", "Q10")])
    monkeypatch.setattr(httpx2, "get", _fake_get({}, []))

    resolve_labels.resolve_labels(BuildConfig())

    written = json.loads(paths.labels_path().read_text())
    assert list(written.keys()) == sorted(written.keys())


# --- 429 handling -----------------------------------------------------------


def test_resolve_retries_rate_limited_batch(tree: Path, monkeypatch: pytest.MonkeyPatch):
    _write_edges([Edge("Q1", "Q10")])
    label_map = {"Q1": "Film One", "Q10": "Actor Ten"}
    calls: list[str] = []

    def get(url, *, params, headers, timeout):
        calls.append(params["ids"])
        if len(calls) == 1:
            return _FakeResponse({}, status_code=429, headers={"Retry-After": "0"})
        return _FakeResponse(_wb_body(label_map, params["ids"].split("|")))

    monkeypatch.setattr(httpx2, "get", get)
    resolve_labels.resolve_labels(BuildConfig())

    assert len(calls) == 2  # the same batch is retried after the 429, not skipped
    written = json.loads(paths.labels_path().read_text())
    assert written == {"Q1": "Film One", "Q10": "Actor Ten"}


# --- resume (the §2.2 regression guard) -------------------------------------


def test_resolve_resume_skips_attempted_including_nulls(
    tree: Path, monkeypatch: pytest.MonkeyPatch
):
    _write_edges([Edge("Q1", "Q10"), Edge("Q2", "Q20")])
    # A prior run resolved Q1 and found Q10 to be a genuine miss (null). BOTH are
    # attempted; neither should be refetched — a null must not be queried forever.
    paths.labels_path().write_text(json.dumps({"Q1": "Film One", "Q10": None}))

    label_map = {"Q2": "Film Two", "Q20": "Actor Twenty"}
    calls: list[list[str]] = []
    monkeypatch.setattr(httpx2, "get", _fake_get(label_map, calls))

    resolve_labels.resolve_labels(BuildConfig())

    requested = {q for batch in calls for q in batch}
    assert requested == {"Q2", "Q20"}  # only the un-attempted QIDs are fetched
    written = json.loads(paths.labels_path().read_text())
    assert written == {"Q1": "Film One", "Q10": None, "Q2": "Film Two", "Q20": "Actor Twenty"}


# --- checkpointing ----------------------------------------------------------


def test_resolve_checkpoint_contains_attempted_only(
    tree: Path, monkeypatch: pytest.MonkeyPatch
):
    # 30 edges -> 60 distinct QIDs -> two batches of [50, 10]. With CHECKPOINT_EVERY=1
    # a checkpoint fires after batch 1; it must contain exactly batch 1's 50 QIDs and
    # none of batch 2's. Seeding all missing QIDs up front (the bug) would write all 60.
    _write_edges([Edge(f"Q{i}", f"Q{1000 + i}") for i in range(30)])
    monkeypatch.setattr(resolve_labels, "CHECKPOINT_EVERY", 1)

    calls: list[list[str]] = []
    observed: dict[str, set[str]] = {}

    def get(url, *, params, headers, timeout):
        ids = params["ids"].split("|")
        calls.append(ids)
        if len(calls) == 2:
            # batch 1 is checkpointed to disk; batch 2 is not yet applied.
            written = json.loads(paths.labels_path().read_text())
            observed["checkpoint_keys"] = set(written)
            observed["batch2"] = set(ids)
        return _FakeResponse(_wb_body({}, ids))  # all misses; attempted-ness is the point

    monkeypatch.setattr(httpx2, "get", get)
    resolve_labels.resolve_labels(BuildConfig())

    assert len(observed["checkpoint_keys"]) == 50
    assert observed["checkpoint_keys"].isdisjoint(observed["batch2"])
