"""End-to-end pipeline test: fake WDQS -> raw cache -> edges.jsonl -> graph/<version>/.

Everything below the HTTP call is real. Only `httpx2.post` is replaced, by a fake WDQS
that serves the binding shape the live endpoint returns (entity URIs, string-typed
counts), so this exercises sparql's flattening and QID extraction, extract's caching,
transform's min_cast/cast_cap policy, and emit's inversion — as one wired pipeline
rather than three isolated stages.

What a unit test can't catch and this can: the stages disagreeing at a seam (file
format, field names, path helpers), and the two properties Phase 1 is judged on —
**cache reuse on re-run** and **byte-identical output**.
"""

import json
import re
import time
from pathlib import Path
from typing import Any

import httpx2
import pytest

from etl import emit, extract, paths, transform
from etl.config import BuildConfig

# --- the fake catalog -------------------------------------------------------------

# (qid, label, sitelinks) per side. Chosen so the pipeline's policy knobs actually bite:
#   * Q2 has 1 cast member  -> dropped by min_cast=2
#   * Q1 has 3 cast members -> trimmed to 2 by cast_cap=2, keeping the top sitelinks
#   * Q10/Q11 appear in films in DIFFERENT years -> the actor->movies inversion has to
#     span year partitions, which is the whole reason extract partitions at all.
#   * Q5 appears in BOTH years, identical cast -> a film with a festival premiere in one
#     year and a wide release in the next. P577 is multi-valued, so the live query really
#     does return it twice; transform must emit it once, at the earlier year.
CATALOG: dict[int, list[tuple[str, str, int, str, str, int]]] = {
    1994: [
        ("Q1", "Pulp Fiction", 150, "Q10", "John Travolta", 100),
        ("Q1", "Pulp Fiction", 150, "Q11", "Samuel L. Jackson", 90),
        ("Q1", "Pulp Fiction", 150, "Q12", "Uma Thurman", 80),
        ("Q2", "Clerks", 60, "Q20", "Brian O'Halloran", 10),
        ("Q5", "Festival Darling", 40, "Q50", "A Lead", 30),
        ("Q5", "Festival Darling", 40, "Q51", "B Lead", 20),
    ],
    1995: [
        ("Q3", "Heat", 120, "Q30", "Robert De Niro", 200),
        ("Q3", "Heat", 120, "Q31", "Al Pacino", 190),
        ("Q4", "Get Shorty", 70, "Q10", "John Travolta", 100),
        ("Q4", "Get Shorty", 70, "Q11", "Samuel L. Jackson", 90),
        ("Q5", "Festival Darling", 40, "Q50", "A Lead", 30),
        ("Q5", "Festival Darling", 40, "Q51", "B Lead", 20),
    ],
}


def _binding(row: tuple[str, str, int, str, str, int]) -> dict[str, dict[str, str]]:
    """One SPARQL result binding: entities are URIs and counts are strings, exactly as the
    live endpoint returns them — that's what sparql._flatten has to unpick. Labels come
    back inline from the query's OPTIONAL rdfs:label clauses; QLever has no 60s wall, so
    there is no separate label-resolution stage."""
    film, film_label, film_sitelinks, actor, actor_label, actor_sitelinks = row
    return {
        "film": {"value": f"http://www.wikidata.org/entity/{film}"},
        "filmLabel": {"value": film_label},
        "filmSitelinks": {"value": str(film_sitelinks)},
        "actor": {"value": f"http://www.wikidata.org/entity/{actor}"},
        "actorLabel": {"value": actor_label},
        "actorSitelinks": {"value": str(actor_sitelinks)},
    }


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


class FakeWDQS:
    """Stands in for query.wikidata.org. Records every request so the tests can assert
    on call counts (cache reuse) and on the User-Agent (etiquette is required — generic
    agents are blocked outright by the real endpoint)."""

    def __init__(self) -> None:
        self.queries: list[str] = []
        self.headers: list[dict[str, str]] = []

    def post(self, **kwargs: Any) -> _FakeResponse:
        query = kwargs["data"]["query"]
        self.queries.append(query)
        self.headers.append(kwargs["headers"])

        match = re.search(r"YEAR\(\?date\) = (\d+)", query)
        assert match, "extract must partition by year"
        rows = CATALOG.get(int(match.group(1)), [])
        return _FakeResponse({"results": {"bindings": [_binding(r) for r in rows]}})


# --- fixtures ---------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda _: None)


@pytest.fixture
def wdqs(monkeypatch: pytest.MonkeyPatch) -> FakeWDQS:
    fake = FakeWDQS()
    monkeypatch.setattr(httpx2, "post", fake.post)
    return fake


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    raw = tmp_path / "raw"
    interim = tmp_path / "interim"
    data = tmp_path / "data"
    raw.mkdir()
    interim.mkdir()
    data.mkdir()
    monkeypatch.setattr(paths, "RAW_DIR", raw)
    monkeypatch.setattr(paths, "INTERIM_DIR", interim)
    monkeypatch.setattr(paths, "GRAPH_DIR", tmp_path / "graph")
    monkeypatch.setattr(paths, "DATA_DIR", data)
    # extract from-imports RAW_DIR, so it needs patching independently of paths.RAW_DIR.
    monkeypatch.setattr(extract, "RAW_DIR", raw)
    return tmp_path


def _cfg(
    *,
    year_from: int = 1994,
    year_to: int = 1995,
    min_sitelinks: int = 5,
    min_cast: int = 2,
    cast_cap: int = 2,
) -> BuildConfig:
    """Config over the fake catalog's two years, with the dials the tests tune."""
    return BuildConfig(
        year_from=year_from,
        year_to=year_to,
        min_sitelinks=min_sitelinks,
        min_cast=min_cast,
        cast_cap=cast_cap,
    )


def _build(cfg: BuildConfig, version: str = "v1") -> Path:
    """The whole pipeline, in the order the orchestrator will run it."""
    extract.extract(cfg)
    transform.transform(cfg)
    return emit.emit(cfg, version)


# --- the run ----------------------------------------------------------------------


def test_pipeline_produces_expected_graph(tree: Path, wdqs: FakeWDQS):
    out = _build(_cfg())
    graph = json.loads((out / "graph.json").read_text())

    # Q2 dropped (1 cast < min_cast=2); Q1 trimmed to its top 2 by actor sitelinks.
    assert graph["movies_to_actors"] == {
        "Q1": ["Q10", "Q11"],
        "Q3": ["Q30", "Q31"],
        "Q4": ["Q10", "Q11"],
        "Q5": ["Q50", "Q51"],
    }
    # The inversion spans year partitions: Q10 played in a 1994 and a 1995 film.
    assert graph["actors_to_movies"] == {
        "Q10": ["Q1", "Q4"],
        "Q11": ["Q1", "Q4"],
        "Q30": ["Q3"],
        "Q31": ["Q3"],
        "Q50": ["Q5"],
        "Q51": ["Q5"],
    }


def test_pipeline_graph_is_symmetric(tree: Path, wdqs: FakeWDQS):
    graph = json.loads((_build(_cfg()) / "graph.json").read_text())
    for movie, cast in graph["movies_to_actors"].items():
        for actor in cast:
            assert movie in graph["actors_to_movies"][actor]
    for actor, films in graph["actors_to_movies"].items():
        for movie in films:
            assert actor in graph["movies_to_actors"][movie]


def test_pipeline_entities_carry_labels_from_wikidata(tree: Path, wdqs: FakeWDQS):
    """Labels survive the full trip: SPARQL response -> raw cache -> edges -> index."""
    graph = json.loads((_build(_cfg()) / "graph.json").read_text())
    assert graph["entities"]["Q1"] == {"label": "Pulp Fiction", "type": "movie", "year": 1994}
    assert graph["entities"]["Q30"] == {"label": "Robert De Niro", "type": "actor"}
    assert "Q2" not in graph["entities"]  # dropped film leaves no orphan entity


def test_pipeline_entities_carry_the_partition_year_as_the_release_year(tree: Path, wdqs: FakeWDQS):
    """The typeahead disambiguator, end to end: the year comes from the partition the film
    was fetched in, never from a second query."""
    graph = json.loads((_build(_cfg()) / "graph.json").read_text())
    assert graph["entities"]["Q1"]["year"] == 1994
    assert graph["entities"]["Q3"]["year"] == 1995


def test_pipeline_cross_partition_film_takes_its_earliest_year(tree: Path, wdqs: FakeWDQS):
    """Q5 is returned by both the 1994 and the 1995 query. It must appear once, dated to the
    premiere — otherwise the year a player sees depends on partition iteration order."""
    graph = json.loads((_build(_cfg()) / "graph.json").read_text())
    assert graph["entities"]["Q5"] == {"label": "Festival Darling", "type": "movie", "year": 1994}
    assert graph["movies_to_actors"]["Q5"] == ["Q50", "Q51"]


def test_pipeline_manifest_describes_the_build(tree: Path, wdqs: FakeWDQS):
    manifest = json.loads((_build(_cfg()) / "manifest.json").read_text())
    assert manifest["counts"] == {"n_movies": 4, "n_actors": 6, "n_edges": 8}
    assert manifest["config"]["min_cast"] == 2
    assert manifest["config"]["cast_cap"] == 2
    assert manifest["query_date"]["from"] is not None


def test_pipeline_interim_line_count_matches_the_emitted_edge_count(tree: Path, wdqs: FakeWDQS):
    """Deduping films across partitions is what makes transform's reported edge count and
    emit's n_edges the same number. They sit next to each other in the CLI's output."""
    out = _build(_cfg())
    lines = [ln for ln in paths.edges_path().read_text().splitlines() if ln.strip()]
    manifest = json.loads((out / "manifest.json").read_text())
    assert len(lines) == manifest["counts"]["n_edges"]


def test_pipeline_sends_contact_user_agent(tree: Path, wdqs: FakeWDQS):
    """WDQS blocks generic/absent agents outright, so this is a hard requirement."""
    _build(_cfg())
    assert wdqs.headers
    for headers in wdqs.headers:
        assert "bacons-law-etl" in headers["User-Agent"]
        assert headers["Accept"] == "application/sparql-results+json"


def test_pipeline_queries_once_per_year(tree: Path, wdqs: FakeWDQS):
    _build(_cfg())
    assert len(wdqs.queries) == 2


# --- the two properties Phase 1 is judged on --------------------------------------


def test_rerun_reuses_raw_cache_and_makes_no_network_calls(tree: Path, wdqs: FakeWDQS):
    """The disk seam's entire purpose: re-running must not re-download the internet."""
    _build(_cfg())
    assert len(wdqs.queries) == 2

    _build(_cfg())
    assert len(wdqs.queries) == 2  # unchanged — second run served entirely from cache


def test_rerun_is_byte_identical(tree: Path, wdqs: FakeWDQS):
    """'Same input, same graph' — the claim that makes two builds diffable."""
    first = (_build(_cfg()) / "graph.json").read_bytes()
    assert (_build(_cfg()) / "graph.json").read_bytes() == first


def test_changing_extract_config_refetches(tree: Path, wdqs: FakeWDQS):
    """min_sitelinks is applied server-side, so a change invalidates the raw cache."""
    _build(_cfg())
    assert len(wdqs.queries) == 2

    _build(_cfg(min_sitelinks=99), version="v2")
    assert len(wdqs.queries) == 4


def test_changing_transform_config_does_not_refetch(tree: Path, wdqs: FakeWDQS):
    """cast_cap is a transform-time dial. Re-tuning it must be free — that separation
    is why the cap lives downstream of the cached seam."""
    _build(_cfg(cast_cap=2))
    assert len(wdqs.queries) == 2

    out = _build(_cfg(cast_cap=3), version="v2")
    assert len(wdqs.queries) == 2  # no new network traffic

    graph = json.loads((out / "graph.json").read_text())
    assert graph["movies_to_actors"]["Q1"] == ["Q10", "Q11", "Q12"]  # cap relaxed


def test_retuned_build_lands_beside_the_old_version(tree: Path, wdqs: FakeWDQS):
    """Versioned directories, not in-place mutation."""
    _build(_cfg(cast_cap=2), version="v1")
    _build(_cfg(cast_cap=3), version="v2")

    v1 = json.loads((paths.graph_version_dir("v1") / "graph.json").read_text())
    v2 = json.loads((paths.graph_version_dir("v2") / "graph.json").read_text())
    assert v1["movies_to_actors"]["Q1"] == ["Q10", "Q11"]
    assert v2["movies_to_actors"]["Q1"] == ["Q10", "Q11", "Q12"]


def test_interrupted_extract_resumes_from_partial_cache(tree: Path, wdqs: FakeWDQS):
    """A pull killed halfway must resume, not restart: only the missing year refetches."""
    extract.extract(_cfg(year_from=1994, year_to=1994))
    assert len(wdqs.queries) == 1

    _build(_cfg())
    assert len(wdqs.queries) == 2  # only 1995 was fetched on the second pass
