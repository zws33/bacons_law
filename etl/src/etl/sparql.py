from typing import NotRequired, TypedDict, cast

import httpx2

from etl.config import BuildConfig
from etl.models import WikidataRow


class SparqlError(RuntimeError):
    """Request failed or returned an unusable body."""

    default_message: str = "Request failed or returned an unusable body."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.default_message)


class _Row(TypedDict):
    film: dict[str, str]
    filmLabel: NotRequired[dict[str, str]]
    articleName: NotRequired[dict[str, str]]
    filmSitelinks: dict[str, str]
    actor: dict[str, str]
    actorLabel: NotRequired[dict[str, str]]
    actorSitelinks: dict[str, str]


class _Results(TypedDict):
    bindings: list[_Row]


class _SparqlResponse(TypedDict):
    results: _Results


def query(query: str, config: BuildConfig) -> list[WikidataRow]:
    headers = {
        "User-Agent": config.user_agent,
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
        raise SparqlError(f"Request failed: {e}") from e
    except ValueError as e:  # non-JSON body (usually an HTML error/timeout page)
        raise SparqlError(f"Request returned a non-JSON body: {e}") from e
    return _flatten(payload)


def _qid_from_uri(uri: str) -> str:
    """Extract the QID from a Wikidata URI."""
    return uri.rsplit("/", 1)[-1]


def _first_bound(row: _Row, *keys: str, fallback: str) -> str:
    """First bound variable among `keys`, else `fallback`.

    An unbound OPTIONAL is ABSENT from the binding object, not present-and-null, so this is
    a .get() chain rather than an `or` chain. The fallback is always the QID: a display
    name may be poor, but it is never missing.
    """
    for key in keys:
        binding = row.get(key)
        if binding is not None:
            return binding["value"]
    return fallback


def _flatten(payload: _SparqlResponse) -> list[WikidataRow]:
    try:
        rows: list[WikidataRow] = []
        for b in payload["results"]["bindings"]:
            film_qid = _qid_from_uri(b["film"]["value"])
            actor_qid = _qid_from_uri(b["actor"]["value"])
            rows.append(
                WikidataRow(
                    film=film_qid,
                    # rdfs:label first, then the enwiki article title. Films are anchored to
                    # an English article, so tier 2 covers the items Wikidata never gave an
                    # English label. Actors have no such anchor and stop at the QID.
                    film_label=_first_bound(b, "filmLabel", "articleName", fallback=film_qid),
                    film_sitelinks=int(b["filmSitelinks"]["value"]),
                    actor=actor_qid,
                    actor_label=_first_bound(b, "actorLabel", fallback=actor_qid),
                    actor_sitelinks=int(b["actorSitelinks"]["value"]),
                )
            )
        return rows
    except (KeyError, TypeError, ValueError) as e:
        raise SparqlError(f"unexpected WDQS response shape: {e}") from e
