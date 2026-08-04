"""Tests for the CLI layer (etl.__main__) — the seam nothing else covered.

This layer went untested through the whole build, which is exactly how
`_config_from_args` shipped mapping --year-from onto a field name that does not
exist (`from_year` vs `year_from`): every stage test constructed BuildConfig
directly, so no test ever went through argparse. The dials only reach the pipeline
through this translation, and a typo here silently mis-configures a real pull.

Two groups:
  * dispatch + translation — stages replaced by recorders, so these assert *what the
    CLI asked for*, not what the pipeline computed;
  * exit status — every failure a user can trigger must be a SystemExit carrying an
    instruction, never a traceback. Callers chain on exit status.
"""

import sys
from pathlib import Path
from typing import Any

import pytest

from etl import __main__ as cli
from etl import emit, paths, transform
from etl.config import BuildConfig
from etl.extract import ExtractStats
from etl.models import Edge
from etl.transform import TransformStats

# --- fixtures / helpers -----------------------------------------------------------


@pytest.fixture
def tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the data/graph trees so no test touches the real ones."""
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
    return tmp_path


class Recorder:
    """Stands in for a stage, capturing the config the CLI handed it."""

    def __init__(self, result: Any = None) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.result = result

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append(args + tuple(kwargs.values()))
        return self.result

    @property
    def config(self) -> BuildConfig:
        assert self.calls, "stage was never invoked"
        return self.calls[0][0]


@pytest.fixture
def stages(monkeypatch: pytest.MonkeyPatch) -> dict[str, Recorder]:
    """Replace all three stages. __main__ from-imports them, so patch its namespace."""
    recorders = {
        "extract": Recorder(ExtractStats(fetched=0, cached=1)),
        "transform": Recorder(TransformStats(edges=1, movies=1, actors=1)),  # a non-empty build
        "emit": Recorder(Path("graph/v1")),
    }
    for name, rec in recorders.items():
        monkeypatch.setattr(cli, name, rec)
    return recorders


def run(monkeypatch: pytest.MonkeyPatch, *argv: str) -> None:
    monkeypatch.setattr(sys, "argv", ["etl", *argv])
    cli.main()


def _edge(movie: str = "Q1", actor: str = "Q10") -> Edge:
    return Edge(
        movie=movie,
        movie_label=f"Film {movie}",
        movie_year=1994,
        actor=actor,
        actor_label=f"Actor {actor}",
    )


# --- dispatch ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("extract", {"extract"}),
        ("transform", {"transform"}),
        ("emit", {"emit"}),
        ("build", {"extract", "transform", "emit"}),
    ],
)
def test_subcommand_runs_only_its_own_stages(
    monkeypatch: pytest.MonkeyPatch, stages: dict[str, Recorder], command: str, expected: set[str]
):
    """The reason per-stage commands exist: `transform` must not re-run extract."""
    run(monkeypatch, command)
    assert {name for name, rec in stages.items() if rec.calls} == expected


def test_build_runs_stages_in_pipeline_order(
    monkeypatch: pytest.MonkeyPatch, stages: dict[str, Recorder]
):
    order: list[str] = []
    for name, rec in stages.items():

        def record(*_a: Any, _n: str = name, _result: Any = rec.result, **_k: Any) -> Any:
            order.append(_n)
            return _result

        monkeypatch.setattr(cli, name, record)

    run(monkeypatch, "build")
    assert order == ["extract", "transform", "emit"]


# --- argument translation (the bug that got away) ---------------------------------


def test_year_flags_reach_the_config(monkeypatch: pytest.MonkeyPatch, stages: dict[str, Recorder]):
    """Regression: these were mapped onto from_year/to_year, which BuildConfig has no
    such fields for — every use of either flag raised TypeError."""
    run(monkeypatch, "extract", "--year-from", "1994", "--year-to", "1996")
    cfg = stages["extract"].config
    assert (cfg.year_from, cfg.year_to) == (1994, 1996)


def test_dial_flags_reach_the_config(monkeypatch: pytest.MonkeyPatch, stages: dict[str, Recorder]):
    run(monkeypatch, "transform", "--cap", "7", "--min-cast", "2", "--min-sitelinks", "9")
    cfg = stages["transform"].config
    assert (cfg.cast_cap, cfg.min_cast, cfg.min_sitelinks) == (7, 2, 9)


def test_omitted_flags_keep_defaults(monkeypatch: pytest.MonkeyPatch, stages: dict[str, Recorder]):
    """Absent flags must fall through to BuildConfig's defaults, not None."""
    run(monkeypatch, "extract")
    assert stages["extract"].config == BuildConfig()


def test_out_version_and_force_reach_emit(
    monkeypatch: pytest.MonkeyPatch, stages: dict[str, Recorder]
):
    run(monkeypatch, "emit", "--out-version", "v3", "--force")
    _cfg, version, force = stages["emit"].calls[0]
    assert (version, force) == ("v3", True)


def test_emit_defaults_to_v1_without_force(
    monkeypatch: pytest.MonkeyPatch, stages: dict[str, Recorder]
):
    run(monkeypatch, "emit")
    _cfg, version, force = stages["emit"].calls[0]
    assert (version, force) == ("v1", False)


# --- exit status ------------------------------------------------------------------


def test_no_subcommand_is_an_error(monkeypatch: pytest.MonkeyPatch):
    with pytest.raises(SystemExit) as exc:
        run(
            monkeypatch,
        )
    assert exc.value.code == 2  # argparse usage error


@pytest.mark.parametrize(
    "argv",
    [
        ("build", "--year-from", "2020", "--year-to", "1990"),
        ("transform", "--cap", "0"),
        ("transform", "--min-cast", "0"),
    ],
)
def test_invalid_config_exits_with_a_message(
    monkeypatch: pytest.MonkeyPatch, stages: dict[str, Recorder], argv: tuple[str, ...]
):
    """Rejected before any stage runs — no partial work on a nonsense config."""
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, *argv)
    assert "invalid config" in str(exc.value.code)
    assert not any(rec.calls for rec in stages.values())


def test_zero_edge_build_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch, stages: dict[str, Recorder]
):
    """The failure this CLI used to report as success. A build that produced nothing
    must be distinguishable by exit status, and must not go on to emit."""
    monkeypatch.setattr(cli, "transform", Recorder(TransformStats(edges=0, movies=0, actors=0)))
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, "build")
    assert exc.value.code != 0
    assert "no edges" in str(exc.value.code)
    assert not stages["emit"].calls


def test_emit_before_transform_exits_with_an_instruction(
    tree: Path, monkeypatch: pytest.MonkeyPatch
):
    """Real stages, no edges.jsonl: the mistake per-stage commands make possible."""
    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, "emit")
    assert "run the transform stage first" in str(exc.value.code)


def test_version_guard_surfaces_as_exit_not_traceback(tree: Path, monkeypatch: pytest.MonkeyPatch):
    """emit's ValueError must reach the user as a message, not a stack trace."""
    transform._write_edges([_edge()])
    emit.emit(BuildConfig(cast_cap=5), "v1")

    with pytest.raises(SystemExit) as exc:
        run(monkeypatch, "emit", "--cap", "9")
    assert "different config" in str(exc.value.code)

    # and --force gets past it
    run(monkeypatch, "emit", "--cap", "9", "--force")


# --- end to end through the CLI ---------------------------------------------------


def test_emit_writes_the_artifact_the_cli_named(tree: Path, monkeypatch: pytest.MonkeyPatch):
    """The path printed/returned is the path written — no hand-built duplicate."""
    transform._write_edges([_edge()])
    run(monkeypatch, "emit", "--out-version", "v9")

    out = paths.graph_version_dir("v9")
    assert (out / "graph.json").exists()
    assert (out / "manifest.json").exists()
