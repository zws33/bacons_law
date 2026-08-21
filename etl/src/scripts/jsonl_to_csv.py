#! /usr/bin/env python3
import argparse
import csv
import itertools
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import TypedDict


class Edge(TypedDict):
    movie: str
    movie_label: str
    movie_sitelinks: int
    movie_year: int
    actor: str
    actor_label: str
    actor_sitelinks: int


ETL_ROOT = Path(__file__).resolve().parents[2]
INPUT = ETL_ROOT / "data" / "interim" / "edges.jsonl"
DATA_DIR = ETL_ROOT / "data"
ACTORS_CSV = DATA_DIR / "actors.csv"
MOVIES_CSV = DATA_DIR / "movies.csv"
EDGES_CSV = DATA_DIR / "edges.csv"

a_columns = ["actor_id", "actor_label", "actor_sitelinks", "actor_search_key"]
m_columns = ["movie_id", "movie_label", "movie_sitelinks", "movie_year", "movie_search_key"]
e_columns = ["movie_id", "actor_id"]

WHITE_SPACE_RE = re.compile(r"\s+")


def make_search_key(label: str) -> str:
    decomposed = unicodedata.normalize("NFKD", label)
    without_marks = "".join(c for c in decomposed if not unicodedata.category(c).startswith("M"))
    folded = without_marks.casefold()
    separated = "".join(c if c.isalnum() else " " for c in folded)
    return WHITE_SPACE_RE.sub(" ", separated).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="transform edges to csv files")
    parser.add_argument("--limit", type=int, default=None, help="Number of lines to consume")
    args = parser.parse_args()

    if not INPUT.exists():
        print(f"Input file {INPUT} does not exist.")
        sys.exit(1)

    with (
        INPUT.open(encoding="utf-8") as jsonl,
        ACTORS_CSV.open("w", encoding="utf-8") as actors_csv,
        MOVIES_CSV.open("w", encoding="utf-8") as movies_csv,
        EDGES_CSV.open("w", encoding="utf-8") as edges_csv,
    ):
        a_writer = csv.DictWriter(actors_csv, fieldnames=a_columns)
        m_writer = csv.DictWriter(movies_csv, fieldnames=m_columns)
        e_writer = csv.DictWriter(edges_csv, fieldnames=e_columns)
        a_writer.writeheader()
        m_writer.writeheader()
        e_writer.writeheader()

        seen_actors = set()
        seen_movies = set()
        edges_count = 0

        for n, line in enumerate(itertools.islice(jsonl, args.limit)):
            try:
                e: Edge = json.loads(line.strip())
            except json.JSONDecodeError as error:
                raise ValueError(f"Error decoding JSON on line {n + 1}") from error
            if e["actor"] not in seen_actors:
                a_writer.writerow(
                    {
                        "actor_id": e["actor"],
                        "actor_label": e["actor_label"],
                        "actor_sitelinks": e["actor_sitelinks"],
                        "actor_search_key": make_search_key(e["actor_label"]),
                    }
                )
                seen_actors.add(e["actor"])
            if e["movie"] not in seen_movies:
                m_writer.writerow(
                    {
                        "movie_id": e["movie"],
                        "movie_label": e["movie_label"],
                        "movie_sitelinks": e["movie_sitelinks"],
                        "movie_year": e["movie_year"],
                        "movie_search_key": make_search_key(e["movie_label"]),
                    }
                )
                seen_movies.add(e["movie"])
            e_writer.writerow({"movie_id": e["movie"], "actor_id": e["actor"]})
            edges_count += 1
        report = {
            "edges": edges_count,
            "actors": len(seen_actors),
            "movies": len(seen_movies),
        }
        print(report)


if __name__ == "__main__":
    main()
