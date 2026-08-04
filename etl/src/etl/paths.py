from pathlib import Path

# This file is etl/src/etl/paths.py → parents[2] is the etl/ project root.
ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
GRAPH_DIR = DATA_DIR / "graph"


def raw_path(year: int) -> Path:
    return RAW_DIR / f"films-{year}.json"


def edges_path() -> Path:
    return INTERIM_DIR / "edges.jsonl"


def graph_version_dir(version: str) -> Path:
    return GRAPH_DIR / version
