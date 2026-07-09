from typing import TypedDict, cast

import httpx2

from etl.config import BuildConfig


class SparqlError(RuntimeError):
    """WDQS request failed or returned an unusable body."""

    default_message: str = "WDQS request failed or returned an unusable body."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.default_message)


class _Binding(TypedDict):
    type: str
    value: str


class _Results(TypedDict):
    bindings: list[dict[str, _Binding]]


class _SparqlResponse(TypedDict):
    results: _Results


def query(query: str, config: BuildConfig) -> list[dict[str, str | int]]:
    headers = {
        "User-Agent": config.user_agent,  # REQUIRED — generic/absent agents are blocked
        "Accept": "application/sparql-results+json",
    }
    try:
        response = httpx2.post(
            url=config.endpoint,
            data={"query": query},
            headers=headers,
            timeout=58,
        )
        _ = response.raise_for_status()
        payload = cast(_SparqlResponse, response.json())

    except httpx2.HTTPError as e:
        raise SparqlError(f"WDQS request failed: {e}") from e
    except ValueError as e:  # non-JSON body (usually an HTML error/timeout page)
        raise SparqlError(f"WDQS returned a non-JSON body: {e}") from e
    return _flatten(payload)


def _qid_from_uri(uri: str) -> str:
    """Extract the QID from a Wikidata URI."""
    return uri.rsplit("/", 1)[-1]


def _flatten(payload: _SparqlResponse) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    for b in payload["results"]["bindings"]:
        rows.append(
            {
                "film": _qid_from_uri(b["film"]["value"]),
                "film_label": b["filmLabel"]["value"],
                "film_sitelinks": int(b["filmSitelinks"]["value"]),
                "actor": _qid_from_uri(b["actor"]["value"]),
                "actor_label": b["actorLabel"]["value"],
                "actor_sitelinks": int(b["actorSitelinks"]["value"]),
            }
        )
    return rows
