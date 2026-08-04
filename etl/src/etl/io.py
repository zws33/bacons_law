import json
from pathlib import Path
from typing import Any

# --- the primitive (mechanism only) ---


def write_atomic(path: Path, text: str) -> None:
    """Write to a temp sibling then rename; an interrupted run never leaves a half-written cache."""
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(text)
        tmp.replace(path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


# --- JSON conveniences (generic serialization, the lingua franca) ---
def read_json(path: Path) -> Any:
    """Parse a required JSON file. Raises on missing/corrupt — caller wants it to exist."""
    with open(path) as f:
        return json.load(f)


def read_json_or_none(path: Path) -> Any | None:
    """Missing OR corrupt → None. The cache-validity path (extract's _cache_is_valid)."""
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError, json.JSONDecodeError:
        return None


# --- JSONL framing (newline-delimited json is generic mechanism, not schema) ---
# The writer lives in transform._write_edges, not here: it streams an Iterable[Edge] so a
# full-range build never materializes every edge, which a path taking a list cannot do.
def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Parse a JSONL file into dicts. dict→domain conversion is the caller's job."""
    records = []
    with open(path) as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records
