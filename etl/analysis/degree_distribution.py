"""M1-M5 for investigation 001 — actor degree distribution and round-ending moves.

Reads the graph artifact and the raw partition cache, writes a provenance-stamped summary.
Network-free, read-only, and **not a pipeline stage** — see analysis/README.md.

The question, the hypotheses, and the thresholds this module resolves in code are documented in
docs/investigations/001-actor-degree-distribution.md. Thresholds were committed to git BEFORE any
measurement existed; they are duplicated here so the verdict is computed rather than judged while
reading output. If you change one, you are changing the pre-registration — say so out loud.
"""

import argparse
import json
import logging
import subprocess
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

from pydantic import ValidationError

import etl.paths as paths
from etl.io import read_json, write_atomic
from etl.models import CachePayload

logger = logging.getLogger(__name__)

# Pre-registered thresholds. See the investigation doc's "Priors and hypotheses".
H1_MIN_GENUINE_SHARE = 0.60
H4_MAX_TOP_DECILE_KILL_RATE = 0.15
H5_MAX_BOTH_MAP_SHARE = 0.10

type Adjacency = dict[str, list[str]]


class RawAggregates(TypedDict):
    """Everything the single pass over data/raw/ collects.

    Sized deliberately: three dicts of ints keyed by graph nodes, plus one set-per-actor
    restricted to degree-1 actors. Storing a set of cast QIDs per film instead would hold
    ~1.5M strings; see scan_raw for why the int suffices.
    """

    film_sitelinks: dict[str, int]
    film_raw_cast_count: dict[str, int]
    actor_sitelinks: dict[str, int]
    degree1_raw_films: dict[str, set[str]]
    partitions_read: int
    rows_read: int


# --- loading ---------------------------------------------------------------------


def load_graph(version: str) -> tuple[Adjacency, Adjacency, dict[str, Any]]:
    """Returns (movies_to_actors, actors_to_movies, entities).

    `entities` is returned for labels only. Nodes are classified by WHICH ADJACENCY MAP
    they key, never by entities[qid]["type"]: that field is built last-write-wins on a flat
    QID-keyed dict, so a QID appearing as both film and cast member gets an arbitrary type
    (github.com/zws33/bacons_law/issues/19).
    """
    graph = read_json(paths.graph_version_dir(version) / "graph.json")
    return graph["movies_to_actors"], graph["actors_to_movies"], graph["entities"]


def load_manifest(version: str) -> dict[str, Any]:
    """The dials that produced this artifact. cast_cap and min_cast come from HERE — never
    hardcoded, because the dial sweep this investigation feeds will change them."""
    return read_json(paths.graph_version_dir(version) / "manifest.json")


def iter_partitions() -> Iterator[CachePayload]:
    """Yield each cached raw partition, validated, oldest first.

    Deliberately duplicates transform._load_rows rather than importing a private name:
    etl/src/etl is the project's one fixed contract, and an investigation is not a reason to
    widen its public surface. Five lines is the cheaper price.
    """
    for path in sorted(paths.RAW_DIR.glob("films-*.json")):
        try:
            yield CachePayload.model_validate(read_json(path))
        except ValidationError as e:
            raise ValueError(f"Failed to load {path}: {e}") from e


# --- the single streaming pass ---------------------------------------------------


def scan_raw(movie_qids: set[str], actor_qids: set[str], degree1_qids: set[str]) -> RawAggregates:
    """One pass over data/raw/. Call once, after the graph is loaded.

    Loading the graph first is what makes a single pass possible: the pass only accumulates
    what the measurements need, keyed by nodes already known to be in the artifact.

    `seen_films` mirrors transform._edges. A film matched by two year partitions (P577 is
    multi-valued, so a festival premiere and a wide release land in different years) carries
    IDENTICAL cast rows both times, because cast comes from wdt:P161 which is date-independent.
    So the pre-cap cast count taken from the first partition is lossless, and the per-film set
    can be released immediately instead of held for the whole run.
    """
    film_sitelinks: dict[str, int] = {}
    film_raw_cast_count: dict[str, int] = {}
    actor_sitelinks: dict[str, int] = {}
    degree1_raw_films: dict[str, set[str]] = defaultdict(set)
    seen_films: set[str] = set()
    partitions_read = 0
    rows_read = 0

    for payload in iter_partitions():
        partitions_read += 1
        rows_read += len(payload.rows)
        fresh: dict[str, set[str]] = defaultdict(set)

        for row in payload.rows:
            film = row["film"]
            actor = row["actor"]
            # Films the min_cast gate dropped are not graph nodes; they are not this
            # investigation's population and would distort every per-film denominator.
            if film not in movie_qids:
                continue
            if film not in seen_films:
                fresh[film].add(actor)
                film_sitelinks.setdefault(film, row["film_sitelinks"])
            if actor in actor_qids:
                actor_sitelinks.setdefault(actor, row["actor_sitelinks"])
            if actor in degree1_qids:
                # A set, so a repeat partition adds nothing — no seen_films guard needed.
                degree1_raw_films[actor].add(film)

        for film, cast in fresh.items():
            film_raw_cast_count[film] = len(cast)
        seen_films.update(fresh)
        logger.info(
            "[%d/102] %d: %d rows, %d new films",
            partitions_read,
            payload.year,
            len(payload.rows),
            len(fresh),
        )

    return RawAggregates(
        film_sitelinks=film_sitelinks,
        film_raw_cast_count=film_raw_cast_count,
        actor_sitelinks=actor_sitelinks,
        degree1_raw_films=dict(degree1_raw_films),
        partitions_read=partitions_read,
        rows_read=rows_read,
    )


# --- helpers ---------------------------------------------------------------------


def decile_buckets(items: list[tuple[str, int]]) -> list[list[str]]:
    """[(qid, sitelinks)] -> 10 equal-COUNT buckets, index 9 = most notable.

    Equal-count, not equal-width: the sitelink distribution is heavily skewed, so equal-width
    buckets would put nearly every film in bucket 0 and make "top decile" meaningless. This
    makes decile 9 mean "the ~4,762 most-notable films", which is the intended reading of
    "films players will actually name".

    Sort key is (sitelinks, numeric qid) ascending — the same tiebreak shape transform._cap_cast
    uses, so ties resolve identically across runs and across machines.
    """
    ordered = sorted(items, key=lambda kv: (kv[1], int(kv[0][1:])))
    n = len(ordered)
    return [[qid for qid, _ in ordered[(n * i) // 10 : (n * (i + 1)) // 10]] for i in range(10)]


def _pct(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _mean(values: list[float] | list[int]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0


def _percentile(sorted_values: list[int], q: float) -> int:
    if not sorted_values:
        return 0
    return sorted_values[min(len(sorted_values) - 1, int(q * len(sorted_values)))]


def _git_head() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=paths.ROOT,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError, FileNotFoundError, OSError:
        return "unknown"


# --- measurements ----------------------------------------------------------------


def m1_degree_distribution(
    actors_to_movies: Adjacency, movies_to_actors: Adjacency, min_cast: int, cast_cap: int
) -> tuple[dict[str, Any], list[str]]:
    """Degree shape, plus a free invariant check on the movie side.

    Movie degree is pinned to [min_cast, cast_cap] by construction: transform drops films below
    min_cast and _cap_cast truncates above cast_cap. If the artifact disagrees, either it is
    wrong or this module's model of it is — either way, reported rather than absorbed.
    """
    actor_degree = {qid: len(films) for qid, films in actors_to_movies.items()}
    histogram = Counter(actor_degree.values())
    ordered = sorted(actor_degree.values())

    violations: list[str] = []
    movie_degrees = sorted({len(cast) for cast in movies_to_actors.values()})
    out_of_range = [d for d in movie_degrees if d < min_cast or d > cast_cap]
    if out_of_range:
        violations.append(
            f"movie degree outside [min_cast={min_cast}, cast_cap={cast_cap}]: {out_of_range}"
        )

    result = {
        "n_actors": len(actor_degree),
        "n_movies": len(movies_to_actors),
        "actor_degree_histogram": {str(k): v for k, v in sorted(histogram.items())},
        "n_degree_1": histogram.get(1, 0),
        "pct_degree_1": _pct(histogram.get(1, 0), len(actor_degree)),
        "median_degree": _percentile(ordered, 0.50),
        "p90_degree": _percentile(ordered, 0.90),
        "max_degree": max(ordered) if ordered else 0,
        "movie_degree_range": [movie_degrees[0], movie_degrees[-1]] if movie_degrees else [],
    }
    return result, violations


def m2_genuine_vs_cap_induced(degree1_qids: set[str], agg: RawAggregates) -> dict[str, Any]:
    """Split degree-1 actors into real one-credit people and cast-cap artifacts.

    The split that decides whether any remedy is warranted: a genuine one-credit actor is
    legitimate game content, while a cap-induced one is the false-rejection defect seen from
    the other side — that actor's other films are ones a player might name and be rejected for.
    """
    genuine = 0
    cap_induced = 0
    anomalous: list[str] = []
    truncation: Counter[int] = Counter()

    for qid in degree1_qids:
        n = len(agg["degree1_raw_films"].get(qid, ()))
        if n == 0:
            # Cannot happen: an actor keys actors_to_movies only via an edge from a film that
            # survived min_cast, so at least one graph-eligible raw row must mention them.
            # Reported separately, never folded into either bucket.
            anomalous.append(qid)
        elif n == 1:
            genuine += 1
        else:
            cap_induced += 1
            truncation[n] += 1

    classified = genuine + cap_induced
    return {
        "n_degree_1": len(degree1_qids),
        "genuine": genuine,
        "cap_induced": cap_induced,
        "genuine_share": _pct(genuine, classified),
        "anomalous_count": len(anomalous),
        "anomalous_sample": sorted(anomalous)[:20],
        "cap_induced_raw_film_count_histogram": {str(k): v for k, v in sorted(truncation.items())},
    }


def m3_kill_availability(
    movies_to_actors: Adjacency, actor_degree: dict[str, int], agg: RawAggregates
) -> dict[str, Any]:
    """How many films offer a one-move round ender, by film notability.

    This is the headline: a kill available from a household-name film is cheap, one reachable
    only through an obscure film is earned. Decile 9 answers H4.
    """
    kill_count = {
        movie: sum(1 for actor in cast if actor_degree[actor] == 1)
        for movie, cast in movies_to_actors.items()
    }
    buckets = decile_buckets([(m, agg["film_sitelinks"].get(m, 0)) for m in movies_to_actors])

    deciles: list[dict[str, Any]] = []
    for index, films in enumerate(buckets):
        sitelinks = [agg["film_sitelinks"].get(m, 0) for m in films]
        deciles.append(
            {
                "decile": index,
                "n_films": len(films),
                "sitelinks_min": min(sitelinks) if sitelinks else 0,
                "sitelinks_max": max(sitelinks) if sitelinks else 0,
                "pct_with_kill_count_ge_1": _pct(
                    sum(1 for m in films if kill_count[m] >= 1), len(films)
                ),
                "mean_kill_count": _mean([kill_count[m] for m in films]),
                "mean_graph_cast_size": _mean([len(movies_to_actors[m]) for m in films]),
            }
        )

    return {
        "deciles": deciles,
        "overall_pct_with_kill_count_ge_1": _pct(
            sum(1 for m in movies_to_actors if kill_count[m] >= 1), len(movies_to_actors)
        ),
        "top_decile_pct_with_kill_count_ge_1": deciles[9]["pct_with_kill_count_ge_1"],
        "metric_caveat": (
            "pct_with_kill_count_ge_1 SATURATES and cannot discriminate: with 9-13 cast and a "
            "6-12% per-actor degree-1 rate, P(at least one) is high everywhere. Read "
            "mean_kill_count / mean_graph_cast_size for the gradient. This flaw was found after "
            "the fact; H4's verdict stands on the metric as pre-registered."
        ),
    }


def m6_degree1_actor_notability(
    movies_to_actors: Adjacency,
    actor_degree: dict[str, int],
    agg: RawAggregates,
    thresholds: tuple[int, ...] = (0, 10, 25, 50),
) -> dict[str, Any]:
    """POST-HOC, not pre-registered. Added after the first run exposed a gap in M3.

    M3 counts a "kill" as any degree-1 cast member, regardless of whether a player has ever
    heard of them. But a kill only exists if someone would NAME that actor — an unrecognizable
    one-credit performer is not an available move, they are invisible. M3 measured film
    notability and ignored actor notability entirely, so its numbers overcount.

    This re-runs kill availability against a recognizability floor on the ACTOR, using sitelinks
    as the proxy. Reported as an observation, never as a hypothesis outcome: the thresholds were
    chosen after seeing the data, so nothing here can confirm or falsify anything.
    """
    sitelinks = agg["actor_sitelinks"]
    degree1 = [qid for qid, degree in actor_degree.items() if degree == 1]
    multi = [qid for qid, degree in actor_degree.items() if degree > 1]

    def profile(qids: list[str]) -> dict[str, Any]:
        values = sorted(sitelinks.get(qid, 0) for qid in qids)
        return {
            "n": len(values),
            "median": _percentile(values, 0.50),
            "p75": _percentile(values, 0.75),
            "p90": _percentile(values, 0.90),
            "p99": _percentile(values, 0.99),
            "max": values[-1] if values else 0,
        }

    by_threshold: list[dict[str, Any]] = []
    film_buckets = decile_buckets([(m, agg["film_sitelinks"].get(m, 0)) for m in movies_to_actors])
    top_decile = set(film_buckets[9])

    for floor in thresholds:
        nameable = {qid for qid in degree1 if sitelinks.get(qid, 0) >= floor}
        films_with_kill = [
            m for m, cast in movies_to_actors.items() if any(a in nameable for a in cast)
        ]
        by_threshold.append(
            {
                "actor_sitelinks_floor": floor,
                "n_degree1_actors_above_floor": len(nameable),
                "pct_all_films_with_nameable_kill": _pct(
                    len(films_with_kill), len(movies_to_actors)
                ),
                "pct_top_decile_films_with_nameable_kill": _pct(
                    sum(1 for m in films_with_kill if m in top_decile), len(top_decile)
                ),
            }
        )

    return {
        "degree_1_sitelink_profile": profile(degree1),
        "multi_credit_sitelink_profile": profile(multi),
        "kill_availability_by_actor_floor": by_threshold,
        "status": "POST-HOC — thresholds chosen after seeing the data; resolves no hypothesis",
    }


def m4_cast_length_vs_notability(
    movies_to_actors: Adjacency,
    actor_degree: dict[str, int],
    agg: RawAggregates,
    cast_cap: int,
) -> dict[str, Any]:
    """Two relationships: notability vs. cast-list length (H3), and the cap boundary (H2).

    H2's mechanism: capping only bites above cast_cap, and when it bites it keeps the most
    notable, who tend to have other credits. Below the cap nothing is filtered, so a
    zero-sitelink one-credit person survives — min_sitelinks gates FILMS, not actors.
    """
    degree1_rate: dict[str, float] = {}
    for movie, cast in movies_to_actors.items():
        degree1_rate[movie] = sum(1 for a in cast if actor_degree[a] == 1) / len(cast)

    buckets = decile_buckets([(m, agg["film_sitelinks"].get(m, 0)) for m in movies_to_actors])
    by_decile = [
        {
            "decile": index,
            "mean_raw_cast_count": _mean([agg["film_raw_cast_count"].get(m, 0) for m in films]),
            "pct_capped": _pct(
                sum(1 for m in films if agg["film_raw_cast_count"].get(m, 0) > cast_cap),
                len(films),
            ),
        }
        for index, films in enumerate(buckets)
    ]

    capped_rates: list[float] = []
    uncapped_rates: list[float] = []
    for movie in movies_to_actors:
        raw = agg["film_raw_cast_count"].get(movie, 0)
        target = capped_rates if raw > cast_cap else uncapped_rates
        target.append(degree1_rate[movie])

    return {
        "cast_cap": cast_cap,
        "by_sitelink_decile": by_decile,
        "n_capped_films": len(capped_rates),
        "n_uncapped_films": len(uncapped_rates),
        "mean_degree1_rate_capped": _mean(capped_rates),
        "mean_degree1_rate_uncapped": _mean(uncapped_rates),
        "bottom_decile_mean_raw_cast": by_decile[0]["mean_raw_cast_count"],
        "top_decile_mean_raw_cast": by_decile[9]["mean_raw_cast_count"],
    }


def m5_both_map_qids(
    movie_qids: set[str],
    actor_qids: set[str],
    entities: dict[str, Any],
    degree1_qids: set[str],
    movies_to_actors: Adjacency,
    actors_to_movies: Adjacency,
) -> dict[str, Any]:
    """QIDs keying both adjacency maps — the offline-measurable part of issue #19's confound.

    The query places no `?actor wdt:P31 wd:Q5` constraint, so anything P161 points at can enter
    as cast. Films doing so are detectable here. Characters, animals, and groups are NOT
    detectable offline and are reported as unmeasured rather than assumed absent.
    """
    both = sorted(movie_qids & actor_qids, key=lambda q: int(q[1:]))
    return {
        "count": len(both),
        "qids": [
            {
                "qid": qid,
                "label": entities.get(qid, {}).get("label", ""),
                "assigned_type": entities.get(qid, {}).get("type", ""),
                "cast_size_as_movie": len(movies_to_actors[qid]),
                "degree_as_actor": len(actors_to_movies[qid]),
            }
            for qid in both
        ],
        "share_of_degree_1": _pct(len(set(both) & degree1_qids), len(degree1_qids)),
        "unmeasured_offline": (
            "Characters, animals, and groups admitted through the same missing P31 constraint "
            "are not detectable from the artifact and need a Wikidata query. This count is a "
            "floor on issue #19's confound, not its size."
        ),
    }


# --- hypothesis resolution -------------------------------------------------------


def resolve_hypotheses(
    m2: dict[str, Any], m3: dict[str, Any], m4: dict[str, Any], m5: dict[str, Any]
) -> dict[str, Any]:
    """Compute CONFIRMED/FALSIFIED against thresholds committed before measurement.

    Deliberately mechanical: a verdict reached while reading output is a verdict that can be
    rationalized. These comparisons are the pre-registration, executed.
    """

    def verdict(passed: bool) -> str:
        return "CONFIRMED" if passed else "FALSIFIED"

    h1 = m2["genuine_share"]
    h2_uncapped = m4["mean_degree1_rate_uncapped"]
    h2_capped = m4["mean_degree1_rate_capped"]
    h3_top = m4["top_decile_mean_raw_cast"]
    h3_bottom = m4["bottom_decile_mean_raw_cast"]
    h4 = m3["top_decile_pct_with_kill_count_ge_1"]
    h5 = m5["share_of_degree_1"]

    return {
        "H1": {
            "predicted": ">=60% of degree-1 actors are genuine, not cap-induced",
            "confidence": "low",
            "value": h1,
            "threshold": H1_MIN_GENUINE_SHARE,
            "result": verdict(h1 >= H1_MIN_GENUINE_SHARE),
        },
        "H2": {
            "predicted": "degree-1 rate is higher in uncapped films than capped films",
            "confidence": "high",
            "value": {"uncapped": h2_uncapped, "capped": h2_capped},
            "result": verdict(h2_uncapped > h2_capped),
        },
        "H3": {
            "predicted": "film notability correlates positively with raw cast-list length",
            "confidence": "medium-high",
            "value": {"top_decile": h3_top, "bottom_decile": h3_bottom},
            "result": verdict(h3_top > h3_bottom),
        },
        "H4": {
            "predicted": "<15% of top-decile films offer a one-move kill",
            "confidence": "medium",
            "value": h4,
            "threshold": H4_MAX_TOP_DECILE_KILL_RATE,
            "result": verdict(h4 < H4_MAX_TOP_DECILE_KILL_RATE),
        },
        "H5": {
            "predicted": "<10% of degree-1 actors are non-human entities (offline-measurable part)",
            "confidence": "medium",
            "value": h5,
            "threshold": H5_MAX_BOTH_MAP_SHARE,
            "result": verdict(h5 < H5_MAX_BOTH_MAP_SHARE),
        },
    }


# --- entry point -----------------------------------------------------------------


def run(version: str) -> dict[str, Any]:
    movies_to_actors, actors_to_movies, entities = load_graph(version)
    manifest = load_manifest(version)
    config = manifest["config"]
    cast_cap = config["cast_cap"]
    min_cast = config["min_cast"]

    movie_qids = set(movies_to_actors)
    actor_qids = set(actors_to_movies)
    actor_degree = {qid: len(films) for qid, films in actors_to_movies.items()}
    degree1_qids = {qid for qid, degree in actor_degree.items() if degree == 1}

    logger.info(
        "graph %s: %d movies, %d actors, %d degree-1 actors",
        version,
        len(movie_qids),
        len(actor_qids),
        len(degree1_qids),
    )

    agg = scan_raw(movie_qids, actor_qids, degree1_qids)

    m1, violations = m1_degree_distribution(actors_to_movies, movies_to_actors, min_cast, cast_cap)
    m2 = m2_genuine_vs_cap_induced(degree1_qids, agg)
    m3 = m3_kill_availability(movies_to_actors, actor_degree, agg)
    m4 = m4_cast_length_vs_notability(movies_to_actors, actor_degree, agg, cast_cap)
    m5 = m5_both_map_qids(
        movie_qids, actor_qids, entities, degree1_qids, movies_to_actors, actors_to_movies
    )

    return {
        "provenance": {
            "graph_version": version,
            "graph_manifest_config": config,
            "graph_counts": manifest["counts"],
            "partitions_read": agg["partitions_read"],
            "rows_read": agg["rows_read"],
            "analysis_commit": _git_head(),
            "generated_at": datetime.now(UTC).isoformat(),
        },
        "m1_degree_distribution": m1,
        "m2_genuine_vs_cap_induced": m2,
        "m3_kill_availability": m3,
        "m4_cast_length_vs_notability": m4,
        "m5_both_map_qids": m5,
        "m6_degree1_actor_notability_POST_HOC": m6_degree1_actor_notability(
            movies_to_actors, actor_degree, agg
        ),
        "hypotheses": resolve_hypotheses(m2, m3, m4, m5),
        "invariant_violations": violations,
    }


def default_out_path() -> Path:
    # paths.ROOT is etl/; the investigation's data lives beside its document.
    return paths.ROOT.parent / "docs" / "investigations" / "001-data" / "summary.json"


def main() -> None:
    parser = argparse.ArgumentParser(prog="analysis.degree_distribution")
    parser.add_argument("--graph-version", dest="version", default="v1")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("-q", "--quiet", action="store_true", help="only warnings and errors")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO, format="%(message)s")

    summary = run(args.version)
    out = args.out or default_out_path()
    out.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(out, json.dumps(summary, indent=2, sort_keys=True) + "\n")

    hypotheses = summary["hypotheses"]
    print(f"\nwrote {out}")
    for name in sorted(hypotheses):
        print(f"  {name}: {hypotheses[name]['result']}")
    if summary["invariant_violations"]:
        print("\nINVARIANT VIOLATIONS:")
        for violation in summary["invariant_violations"]:
            print(f"  {violation}")


if __name__ == "__main__":
    main()
