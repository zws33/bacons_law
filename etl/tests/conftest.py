"""Pytest configuration for the guided harness.

Adds:
  - a `live` marker + `--run-live` flag so the one networked test is OFF by default;
  - a per-stage build-progress dashboard printed after every run.

No pipeline code is imported here — keeps collection safe while modules are empty.
"""

import collections

import pytest

# Ordered stages. The key is matched as a substring of each test's node id.
STAGE_LABELS = {
    "test_00": "Stage 0 · shared types  (config / models / paths)",
    "test_01": "Stage 1 · extract        (sparql + fetch loop)",
    "test_02": "Stage 2 · transform      (filter / cap / fold)",
    "test_03": "Stage 3 · emit           (invert / index / manifest)",
    "test_04": "Stage 4 · pipeline       (end-to-end + CLI)",
}


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live: hits the real WDQS endpoint; needs --run-live"
    )


def pytest_addoption(parser):
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="also run tests that hit the real Wikidata endpoint (network).",
    )


def pytest_collection_modifyitems(config, items):
    """Skip `live` tests unless --run-live is passed — the suite is offline by default."""
    if config.getoption("--run-live"):
        return
    skip_live = pytest.mark.skip(reason="needs --run-live (makes a network call)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Print a friendly per-stage progress map so you always know what's left."""
    tally = collections.defaultdict(lambda: collections.Counter())
    for outcome in ("passed", "failed", "error", "skipped"):
        for rep in terminalreporter.stats.get(outcome, []):
            # count each test once: passes/fails at the call phase, skips wherever
            if outcome in ("passed", "failed") and getattr(rep, "when", "call") != "call":
                continue
            # don't hold the opt-in live network test against a finished stage
            if outcome == "skipped":
                longrepr = getattr(rep, "longrepr", None)
                reason = longrepr[2] if isinstance(longrepr, tuple) and len(longrepr) == 3 else ""
                if "--run-live" in (reason or ""):
                    continue
            node = getattr(rep, "nodeid", "")
            for key in STAGE_LABELS:
                if key in node:
                    tally[key][outcome] += 1
                    break

    tr = terminalreporter
    tr.write_sep("=", "Bacon's Law ETL — build progress")
    for key, label in STAGE_LABELS.items():
        t = tally[key]
        broken = t["failed"] + t["error"]
        if broken:
            icon, note = "❌", f"{broken} failing — fix these next"
        elif t["passed"] and not t["skipped"]:
            icon, note = "✅", f"{t['passed']} passing"
        elif t["passed"]:
            icon, note = "🚧", f"{t['passed']} passing, {t['skipped']} to go"
        else:
            icon, note = "⬜", "not started"
        tr.line(f"  {icon}  {label} — {note}")
    tr.line("")
    tr.line("  ✅ done    🚧 in progress    ⬜ not started    ❌ failing")
