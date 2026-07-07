"""Shared helpers + fixtures for the guided test harness.

Nothing here imports your pipeline code at module load time. Everything loads
*lazily* through `require()` so that an empty or half-written module can never
break collection of the whole suite — it just makes the tests that need it SKIP.
"""

import importlib
import json

import pytest


def require(module: str, *attrs):
    """Import `etl.<module>` and return the requested attribute(s).

    Behaviour is tuned for building from scratch:
      - module/attr not written yet      -> pytest.skip (grey, "not built")
      - Python syntax error in your file -> pytest.fail with file + line (red)
      - a missing dependency you own      -> pytest.skip (build the dep first)
      - a missing installed package       -> pytest.fail with an install hint

    Returns the module if no attrs are named, a single object for one attr, or a
    tuple for several.
    """
    full = f"etl.{module}"
    try:
        mod = importlib.import_module(full)
    except SyntaxError as exc:  # your most likely error while learning Python
        pytest.fail(
            f"Syntax error in {exc.filename or full} on line {exc.lineno}: {exc.msg}\n"
            f"    Fix the typo/indentation there, then re-run.",
            pytrace=False,
        )
    except ModuleNotFoundError as exc:
        name = exc.name or ""
        if name == full or name == f"etl.{module}":
            pytest.skip(f"{full} not created yet — build it next.")
        if name.startswith("etl"):
            pytest.skip(f"{full} can't import yet because {name} isn't built.")
        pytest.fail(
            f"{full} needs the package '{name}', which isn't installed.\n"
            f"    Try:  uv sync   (or  uv add {name} )",
            pytrace=False,
        )
    except ImportError as exc:  # e.g. `from etl.models import Actor` before Actor exists
        pytest.skip(f"{full} isn't fully implemented yet ({exc}).")

    if not attrs:
        return mod
    missing = [a for a in attrs if not hasattr(mod, a)]
    if missing:
        names = ", ".join(missing)
        pytest.skip(f"{full} is missing {names} — not implemented yet.")
    resolved = [getattr(mod, a) for a in attrs]
    return resolved[0] if len(resolved) == 1 else tuple(resolved)


# --------------------------------------------------------------------------- #
# Factories — build inputs from YOUR models so the harness tests those too.
# --------------------------------------------------------------------------- #

def make_film(qid: str, *cast: tuple[str, int], sitelinks: int = 100):
    """make_film("Q1", ("Q10", 90), ("Q11", 80)) -> a Film with two cast members."""
    Actor, Film = require("models", "Actor", "Film")
    film = Film(qid, f"label-{qid}", sitelinks)
    for actor_qid, links in cast:
        film.cast[actor_qid] = Actor(actor_qid, f"label-{actor_qid}", links)
    return film


def make_edge(movie: str, actor: str):
    Edge = require("models", "Edge")
    return Edge(movie, f"label-{movie}", actor, f"label-{actor}")


def write_raw(directory, year: int, rows: list[dict], *, min_sitelinks=5, require_enwiki=True):
    """Write a Stage-1-shaped raw wrapper file into `directory`."""
    payload = {
        "year": year,
        "fetched_at": "2026-07-07T00:00:00+00:00",
        "endpoint": "https://query.wikidata.org/sparql",
        "min_sitelinks": min_sitelinks,
        "require_enwiki": require_enwiki,
        "row_count": len(rows),
        "rows": rows,
    }
    path = directory / f"films-{year}.json"
    path.write_text(json.dumps(payload))
    return path


def row(film, actor, *, film_sitelinks=100, actor_sitelinks=50):
    """A single denormalized (film, actor) row, as Stage 1 flattens it."""
    return {
        "film": film,
        "film_label": f"label-{film}",
        "film_sitelinks": film_sitelinks,
        "actor": actor,
        "actor_label": f"label-{actor}",
        "actor_sitelinks": actor_sitelinks,
    }


# --------------------------------------------------------------------------- #
# Canned data (no network).
# --------------------------------------------------------------------------- #

# A realistic SPARQL-JSON response: entity URIs (not bare QIDs) and STRING counts.
# Your parser must strip the URIs to QIDs and int() the counts.
SPARQL_PAYLOAD = {
    "results": {
        "bindings": [
            {
                "film": {"type": "uri", "value": "http://www.wikidata.org/entity/Q25188"},
                "filmLabel": {"type": "literal", "value": "Inception"},
                "filmSitelinks": {"type": "literal", "value": "120"},
                "actor": {"type": "uri", "value": "http://www.wikidata.org/entity/Q38111"},
                "actorLabel": {"type": "literal", "value": "Leonardo DiCaprio"},
                "actorSitelinks": {"type": "literal", "value": "210"},
            },
            {
                "film": {"type": "uri", "value": "http://www.wikidata.org/entity/Q25188"},
                "filmLabel": {"type": "literal", "value": "Inception"},
                "filmSitelinks": {"type": "literal", "value": "120"},
                "actor": {"type": "uri", "value": "http://www.wikidata.org/entity/Q40096"},
                "actorLabel": {"type": "literal", "value": "Joseph Gordon-Levitt"},
                "actorSitelinks": {"type": "literal", "value": "95"},
            },
        ]
    }
}

# Flat rows for the end-to-end pipeline test. Q10 bridges two films (the chain).
PIPELINE_ROWS = [
    row("Q1", "Q10", actor_sitelinks=90),
    row("Q1", "Q11", actor_sitelinks=80),
    row("Q1", "Q12", actor_sitelinks=70),
    row("Q2", "Q10", actor_sitelinks=90),
    row("Q2", "Q13", actor_sitelinks=60),
    row("Q2", "Q14", actor_sitelinks=50),
]


class FakeResponse:
    """Stands in for an httpx response so HTTP-client tests need no network."""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload
