"""CLI for the three-stage graph build.

Each stage is exposed on its own because the disk seam is the point: extract is slow and
rate-limited, transform and emit are pure and fast. Tuning the cap should cost a
`transform && emit`, never a re-pull. `build` is the from-scratch path that runs all three.
"""

import argparse
from dataclasses import replace

from etl.config import BuildConfig
from etl.emit import emit
from etl.extract import extract
from etl.transform import transform


def _config_from_args(args: argparse.Namespace) -> BuildConfig:
    overrides = {
        "year_from": args.year_from,
        "year_to": args.year_to,
        "cast_cap": args.cap,
        "min_sitelinks": args.min_sitelinks,
        "min_cast": args.min_cast,
    }
    overrides = {k: v for k, v in overrides.items() if v is not None}
    return replace(BuildConfig(), **overrides)


def _add_config_args(parser: argparse.ArgumentParser) -> None:
    """The gameplay dials. Shared by every subcommand so the manifest a stage writes
    always reflects the same knobs the earlier stages were run with."""
    parser.add_argument("--year-from", dest="year_from", type=int)
    parser.add_argument("--year-to", dest="year_to", type=int)
    parser.add_argument("--cap", type=int, help="cast_cap: top-N actors per film")
    parser.add_argument("--min-sitelinks", dest="min_sitelinks", type=int)
    parser.add_argument("--min-cast", dest="min_cast", type=int)


def _add_output_args(parser: argparse.ArgumentParser) -> None:
    # --out-version, not --version: argparse convention reserves the latter for the
    # program's own version, and the manifest already has an unrelated schema_version.
    parser.add_argument(
        "--out-version",
        dest="out_version",
        default="v1",
        help="artifact directory under graph/ (default: v1)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing artifact built with different config",
    )


def _run_extract(config: BuildConfig) -> None:
    stats = extract(config)
    print(f"extract: {stats.fetched} fetched, {stats.cached} cached")


def _run_transform(config: BuildConfig) -> int:
    edges_count = transform(config)
    print(f"transform: {edges_count} edges")
    if edges_count == 0:
        # A build that produced nothing is a failed build, not a quiet success — callers
        # chaining on exit status must be able to tell the difference.
        raise SystemExit("no edges were generated; check the year range and filters")
    return edges_count


def _run_emit(config: BuildConfig, args: argparse.Namespace) -> None:
    out = emit(config, args.out_version, force=args.force)
    print(f"emit: {out}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="etl")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="extract → transform → emit")
    _add_config_args(build)
    _add_output_args(build)

    extract_cmd = sub.add_parser("extract", help="stage 1 only — SPARQL → data/raw/")
    _add_config_args(extract_cmd)

    transform_cmd = sub.add_parser("transform", help="stage 2 only — data/raw/ → edges.jsonl")
    _add_config_args(transform_cmd)

    emit_cmd = sub.add_parser("emit", help="stage 3 only — edges.jsonl → graph/<version>/")
    _add_config_args(emit_cmd)
    _add_output_args(emit_cmd)

    args = parser.parse_args()
    try:
        config = _config_from_args(args)
    except ValueError as e:
        raise SystemExit(f"invalid config: {e}") from e

    try:
        if args.command == "extract":
            _run_extract(config)
        elif args.command == "transform":
            _run_transform(config)
        elif args.command == "emit":
            _run_emit(config, args)
        else:
            _run_extract(config)
            _run_transform(config)
            _run_emit(config, args)
    except ValueError as e:
        raise SystemExit(str(e)) from e


if __name__ == "__main__":
    main()
