"""Tests for the extract stage (etl.extract) — all network-free.

Three seams:
  * render_query   — the SPARQL string is fully templated from config;
  * _cache_is_valid — when a cached year may be reused vs. re-fetched
                      (including the stale-format / corrupt-file guards);
  * extract()      — the loop: skip valid caches, fetch + wrap the rest,
                      re-fetch when the extract config changes.

sparql.query is monkeypatched throughout and RAW_DIR is redirected to a
tmp dir, so nothing hits the network or the real data/ tree.
"""

import json
import logging
import time
from pathlib import Path

import pytest

from etl import extract, paths, sparql
from etl.config import BuildConfig


@pytest.fixture
def raw_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect RAW_DIR to a tmp dir for both the paths helper and extract()."""
    d = tmp_path / "raw"
    d.mkdir()
    monkeypatch.setattr(paths, "RAW_DIR", d)
    monkeypatch.setattr(extract, "RAW_DIR", d)
    return d


def _row(film: str = "Q1", actor: str = "Q10") -> dict[str, str | int]:
    return {
        "film": film,
        "film_sitelinks": 100,
        "actor": actor,
        "actor_sitelinks": 50,
    }


def _write_cache(
    path: Path, *, min_sitelinks: int, require_enwiki: bool, rows: list | None = None
) -> None:
    """Write a current-format (metadata-wrapped) raw cache file."""
    path.write_text(
        json.dumps(
            {
                "year": 1994,
                "fetched_at": "2020-01-01T00:00:00+00:00",
                "endpoint": "https://query.wikidata.org/sparql",
                "min_sitelinks": min_sitelinks,
                "require_enwiki": require_enwiki,
                "row_count": len(rows or []),
                "rows": rows or [],
            }
        )
    )


# --- render_query -----------------------------------------------------------


def test_render_query_templated_from_config():
    q = extract.render_query(1994, BuildConfig(min_sitelinks=7))
    assert "YEAR(?date) = 1994" in q
    assert "?filmSitelinks >= 7" in q
    assert "en.wikipedia.org" in q


def test_render_query_omits_enwiki_block_when_disabled():
    assert "en.wikipedia.org" not in extract.render_query(1994, BuildConfig(require_enwiki=False))


def test_render_query_excludes_documentary_and_tv_film():
    q = extract.render_query(1994, BuildConfig())
    assert f"FILTER NOT EXISTS {{ ?film wdt:P31 wd:{extract.DOCUMENTARY} }}" in q
    assert f"FILTER NOT EXISTS {{ ?film wdt:P31 wd:{extract.TV_FILM} }}" in q


# --- _cache_is_valid --------------------------------------------------------


def test_cache_missing_file_is_invalid(raw_dir: Path):
    assert extract._cache_is_valid(BuildConfig(), 1994) is False


def test_cache_matching_config_is_valid(raw_dir: Path):
    _write_cache(raw_dir / "films-1994.json", min_sitelinks=5, require_enwiki=True)
    assert extract._cache_is_valid(BuildConfig(min_sitelinks=5, require_enwiki=True), 1994)


def test_cache_min_sitelinks_mismatch_is_invalid(raw_dir: Path):
    _write_cache(raw_dir / "films-1994.json", min_sitelinks=5, require_enwiki=True)
    assert extract._cache_is_valid(BuildConfig(min_sitelinks=7), 1994) is False


def test_cache_require_enwiki_mismatch_is_invalid(raw_dir: Path):
    _write_cache(raw_dir / "films-1994.json", min_sitelinks=5, require_enwiki=True)
    assert extract._cache_is_valid(BuildConfig(require_enwiki=False), 1994) is False


def test_cache_stale_bare_list_is_invalid(raw_dir: Path):
    # Old extract wrote a bare JSON list; the guard must not crash on .get().
    (raw_dir / "films-1994.json").write_text(json.dumps([_row()]))
    assert extract._cache_is_valid(BuildConfig(), 1994) is False


def test_cache_corrupt_json_is_invalid(raw_dir: Path):
    (raw_dir / "films-1994.json").write_text("{ half-written")
    assert extract._cache_is_valid(BuildConfig(), 1994) is False


# --- extract() --------------------------------------------------------------


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never actually sleep between fetches during tests."""
    monkeypatch.setattr(time, "sleep", lambda _: None)


def test_extract_fetches_and_wraps_rows(raw_dir: Path, monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []

    def fake_query(q: str, cfg: BuildConfig):
        calls.append(q)
        return [_row("Q1", "Q10")]

    monkeypatch.setattr(sparql, "query", fake_query)
    cfg = BuildConfig(year_from=1994, year_to=1994, min_sitelinks=6)
    extract.extract(cfg)

    data = json.loads((raw_dir / "films-1994.json").read_text())
    assert data["rows"] == [_row("Q1", "Q10")]
    assert data["row_count"] == 1
    assert data["year"] == 1994
    assert data["min_sitelinks"] == 6
    assert data["require_enwiki"] == cfg.require_enwiki
    assert len(calls) == 1


def test_extract_skips_valid_cached_year(raw_dir: Path, monkeypatch: pytest.MonkeyPatch):
    _write_cache(raw_dir / "films-1994.json", min_sitelinks=5, require_enwiki=True, rows=[_row()])

    def boom(q: str, cfg: BuildConfig):
        raise AssertionError("network query should not run for a valid cache")

    monkeypatch.setattr(sparql, "query", boom)
    extract.extract(BuildConfig(year_from=1994, year_to=1994))  # min_sitelinks=5 default


def test_extract_refetches_when_config_changes(raw_dir: Path, monkeypatch: pytest.MonkeyPatch):
    _write_cache(raw_dir / "films-1994.json", min_sitelinks=5, require_enwiki=True, rows=[_row()])
    called = False

    def fake_query(q: str, cfg: BuildConfig):
        nonlocal called
        called = True
        return [_row("Q2", "Q20")]

    monkeypatch.setattr(sparql, "query", fake_query)
    extract.extract(BuildConfig(year_from=1994, year_to=1994, min_sitelinks=7))

    assert called
    data = json.loads((raw_dir / "films-1994.json").read_text())
    assert data["min_sitelinks"] == 7
    assert data["rows"] == [_row("Q2", "Q20")]


def test_extract_refetches_stale_bare_list_without_crashing(
    raw_dir: Path, monkeypatch: pytest.MonkeyPatch
):
    (raw_dir / "films-1994.json").write_text(json.dumps([_row()]))  # old format
    monkeypatch.setattr(sparql, "query", lambda q, cfg: [_row("Q9", "Q90")])
    extract.extract(BuildConfig(year_from=1994, year_to=1994))

    data = json.loads((raw_dir / "films-1994.json").read_text())
    assert isinstance(data, dict)
    assert data["rows"] == [_row("Q9", "Q90")]


def test_extract_skips_failed_year_and_reports(
    raw_dir: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
):
    # One year's WDQS query fails (SparqlError — what sparql.query actually raises);
    # the other years must still be fetched, and the run must exit non-zero listing it.
    def fake_query(q: str, cfg: BuildConfig):
        if "YEAR(?date) = 1995" in q:
            raise sparql.SparqlError("WDQS request failed: 504")
        return [_row("Q1", "Q10")]

    monkeypatch.setattr(sparql, "query", fake_query)
    with caplog.at_level(logging.WARNING), pytest.raises(SystemExit) as exc:
        extract.extract(BuildConfig(year_from=1994, year_to=1996))

    assert "1995" in str(exc.value)
    assert (raw_dir / "films-1994.json").exists()
    assert (raw_dir / "films-1996.json").exists()
    assert not (raw_dir / "films-1995.json").exists()  # the failed year was skipped, not written
    assert any(
        "1995" in r.getMessage() and "failed" in r.getMessage().lower() for r in caplog.records
    )
