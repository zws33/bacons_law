"""Stage 3 — data/interim/edges.jsonl → data/graph/<version>/.

No network and no gameplay policy: every filtering decision (min_cast, cast_cap) already
fired in transform. This stage only inverts, indexes, and serializes.
"""

import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import etl.paths as paths
from etl.config import BuildConfig
from etl.io import read_json_or_none, read_jsonl, write_atomic
from etl.models import Edge, Entity, Manifest, ManifestConfig, QueryDateRange

SCHEMA_VERSION = 3

type AdjacencyGraph = tuple[dict[str, set[str]], dict[str, set[str]]]


def emit(config: BuildConfig, version: str, force: bool = False) -> Path:
    """Build the versioned artifact from the interim edge list. Returns its directory."""
    edges = _load_edges()
    if not edges:
        raise ValueError(f"{paths.edges_path()} has no edges; run transform first")

    _check_version_is_free(config, version, force)

    movies_to_actors, actors_to_movies = _build_adjacency(edges)
    graph = {
        "movies_to_actors": _sorted_adjacency(movies_to_actors),
        "actors_to_movies": _sorted_adjacency(actors_to_movies),
        "entities": _build_entities(edges),
    }
    manifest: Manifest = {
        "schema_version": SCHEMA_VERSION,
        "version": version,
        "source": "wikidata",
        "query_date": _query_date_range(),
        "generated_at": datetime.now(UTC).isoformat(),
        "config": _manifest_config(config),
        # All three describe the ARTIFACT, so all three are deduplicated. n_edges was
        # len(edges) — the interim file's line count, which is larger whenever a film
        # appears in more than one year partition (P577 is multi-valued, so a festival
        # premiere and a wide release land in different years). Summing the adjacency
        # sets counts distinct pairs and cannot drift from the graph beside it.
        "counts": {
            "n_movies": len(movies_to_actors),
            "n_actors": len(actors_to_movies),
            "n_edges": sum(len(cast) for cast in movies_to_actors.values()),
        },
    }

    out = paths.graph_version_dir(version)
    out.mkdir(parents=True, exist_ok=True)
    write_atomic(out / "graph.json", json.dumps(graph, sort_keys=True) + "\n")
    write_atomic(out / "manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return out


def _manifest_config(config: BuildConfig) -> ManifestConfig:
    return {
        "min_sitelinks": config.min_sitelinks,
        "min_cast": config.min_cast,
        "cast_cap": config.cast_cap,
        "year_from": config.year_from,
        "year_to": config.year_to,
    }


def _check_version_is_free(config: BuildConfig, version: str, force: bool) -> None:
    """A version is an immutable identity, not a filename."""

    existing = read_json_or_none(paths.graph_version_dir(version) / "manifest.json")
    if force or not isinstance(existing, dict):
        return

    previous = existing.get("config")
    current = _manifest_config(config)
    if previous != current:
        changed = sorted(
            k for k in current if not isinstance(previous, dict) or previous.get(k) != current[k]
        )
        raise ValueError(
            f"graph/{version} was built with different config ({', '.join(changed)} differ); "
            f"emit a new version or pass force=True to overwrite"
        )


def _load_edges() -> list[Edge]:
    path = paths.edges_path()
    try:
        return [Edge(**r) for r in read_jsonl(path)]
    except FileNotFoundError as e:
        raise ValueError(f"{path} does not exist; run the transform stage first") from e
    except TypeError as e:
        raise ValueError(f"Failed to load edges from {path}: {e}") from e


def _build_adjacency(edges: list[Edge]) -> AdjacencyGraph:
    """Build both adjacency directions from the edge list."""
    movies_to_actors: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        movies_to_actors[e.movie].add(e.actor)

    actors_to_movies: dict[str, set[str]] = defaultdict(set)
    for movie, actors in movies_to_actors.items():
        for actor in actors:
            actors_to_movies[actor].add(movie)

    return movies_to_actors, actors_to_movies


def _build_entities(edges: list[Edge]) -> dict[str, Entity]:
    """qid → Entity: the typeahead index Phase 4 search resolves names against.

    Movies carry `year` so a client can render "The Mummy (1999)" and let the player pick
    which one they meant — English titles are not unique, and the QID is not something a
    player can type. Actors have no year and get no key.

    Assignment is last-write-wins, which is only safe because transform emits each film from
    exactly one partition; without that dedupe a film in two years would take whichever
    iterated last.
    """
    entities: dict[str, Entity] = {}
    for e in edges:
        entities[e.movie] = {
            "label": e.movie_label,
            "type": "movie",
            "year": e.movie_year,
            "sitelinks": e.movie_sitelinks,
        }
        entities[e.actor] = {
            "label": e.actor_label,
            "type": "actor",
            "sitelinks": e.actor_sitelinks,
        }
    return entities


def _sorted_adjacency(adj: dict[str, set[str]]) -> dict[str, list[str]]:
    """Sets → sorted lists. JSON has no set type; sorting on write is what makes two
    builds of the same input byte-identical. The Kotlin loader reads them back as Sets."""
    return {k: sorted(v) for k, v in adj.items()}


def _query_date_range() -> QueryDateRange:
    """Min/max fetched_at across the raw cache (D6). A pull can span days; record the span."""
    # Duck-typed on purpose: provenance needs only fetched_at. Validating the full header
    # here would drop a partition written by an older extract from the recorded span
    # instead of reporting it.
    stamps: list[str] = []
    for path in sorted(paths.RAW_DIR.glob("films-*.json")):
        header = read_json_or_none(path)
        if isinstance(header, dict) and "fetched_at" in header:
            stamps.append(header["fetched_at"])
    if not stamps:
        return {"from": None, "to": None}
    return {"from": min(stamps), "to": max(stamps)}
