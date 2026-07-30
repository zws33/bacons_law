import logging
import math
import time
from itertools import batched
from typing import NamedTuple

import httpx2
from pydantic import BaseModel

import etl.paths as paths
from etl.config import BuildConfig
from etl.io import read_json_or_none, read_jsonl, write_json
from etl.models import Edge

logger = logging.getLogger(__name__)

API_URL = "https://www.wikidata.org/w/api.php"
CHECKPOINT_EVERY = 50


class Label(BaseModel):
    language: str
    value: str


class Entity(BaseModel):
    type: str
    id: str
    labels: dict[str, Label]


class WBEntitiesResponse(BaseModel):
    entities: dict[str, Entity]  # The value is a dict with "type", "id", and "labels" keys


def _load_edges() -> list[Edge]:
    path = paths.edges_path()
    try:
        return [Edge(**r) for r in read_jsonl(path)]
    except FileNotFoundError as e:
        raise ValueError(f"{path} does not exist; run the transform stage first") from e
    except TypeError as e:
        raise ValueError(f"Failed to load edges from {path}: {e}") from e


class ResolveLabelsStats(NamedTuple):
    n_labels: int


def _write_labels(labels: dict[str, str | None]) -> None:
    write_json(paths.labels_path(), dict(sorted(labels.items())))


def resolve_labels(cfg: BuildConfig) -> ResolveLabelsStats:
    edges = _load_edges()
    movies = {e.movie for e in edges}
    actors = {e.actor for e in edges}
    all_qids = movies | actors
    existing = read_json_or_none(paths.labels_path()) or {}
    missing_qids = all_qids - existing.keys()

    labels: dict[str, str | None] = dict(existing)

    logger.info("Fetching labels for %d QIDs", len(missing_qids))

    headers = {
        "User-Agent": cfg.user_agent,
        "Accept": "application/json",
    }

    n_batches = math.ceil(len(missing_qids) / 50)
    for i, batch in enumerate(batched(missing_qids, 50, strict=False)):
        logger.info("Fetching batch %d/%d", i + 1, n_batches)
        params = {
            "action": "wbgetentities",
            "format": "json",
            "props": "labels",
            "languages": "en",
            "ids": "|".join(batch),
        }
        while True:
            resp = httpx2.get(API_URL, params=params, headers=headers, timeout=30)
            if resp.status_code == 429:
                time.sleep(int(resp.headers.get("Retry-After", "5")))
                continue
            break
        resp.raise_for_status()
        data = WBEntitiesResponse.model_validate(resp.json())

        labels.update({qid: None for qid in batch})
        for entity in data.entities.values():
            label = entity.labels.get("en")
            if label is not None:
                labels[entity.id] = label.value

        if (i + 1) % CHECKPOINT_EVERY == 0:
            _write_labels(labels)
            logger.info(
                "checkpoint: %d/%d QIDs written", len(labels) - len(existing), len(missing_qids)
            )

    _write_labels(labels)
    return ResolveLabelsStats(n_labels=sum(v is not None for v in labels.values()))
