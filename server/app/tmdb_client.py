from typing import Protocol

import httpx2
from pydantic import BaseModel

from app.models import MovieCreditsResult, MovieSearchResult, PersonSearchResult

_TMDB_BASE = "https://api.themoviedb.org/3"


class _TmdbMovie(BaseModel):
    id: int
    title: str
    release_date: str | None = None
    poster_path: str | None = None


class _TmdbMoveSearchResponse(BaseModel):
    results: list[_TmdbMovie]


class _TmdbPerson(BaseModel):
    id: int
    name: str
    profile_path: str | None = None


class _TmdbPersonSearchResponse(BaseModel):
    results: list[_TmdbPerson]


class _TmdbCastMember(BaseModel):
    id: int


class _TmdbCreditsResponse(BaseModel):
    id: int
    cast: list[_TmdbCastMember]


class TmdbClient(Protocol):
    async def search_movies(self, query: str) -> list[MovieSearchResult]: ...

    async def search_people(self, query: str) -> list[PersonSearchResult]: ...

    async def get_movie_credits(self, movie_id: int) -> MovieCreditsResult: ...


class HttpxTmdbClient:
    def __init__(self, api_key: str, http_client: httpx2.AsyncClient) -> None:
        self._api_key = api_key
        self._http = http_client

    async def search_movies(self, query: str) -> list[MovieSearchResult]:
        r = await self._http.get(
            url=f"{_TMDB_BASE}/search/movie", params={"query": query, "api_key": self._api_key}
        )
        r.raise_for_status()
        parsed = _TmdbMoveSearchResponse.model_validate(r.json())
        return [
            MovieSearchResult(
                id=m.id,
                title=m.title,
                release_year=(m.release_date or "")[:4] or None,
                poster_path=m.poster_path,
            )
            for m in parsed.results
        ]

    async def search_people(self, query: str) -> list[PersonSearchResult]:
        r = await self._http.get(
            url=f"{_TMDB_BASE}/search/person", params={"query": query, "api_key": self._api_key}
        )
        r.raise_for_status()
        parsed = _TmdbPersonSearchResponse.model_validate(r.json())
        return [
            PersonSearchResult(id=p.id, name=p.name, profile_path=p.profile_path)
            for p in parsed.results
        ]

    async def get_movie_credits(self, movie_id: int) -> MovieCreditsResult:
        r = await self._http.get(
            url=f"{_TMDB_BASE}/movie/{movie_id}/credits", params={"api_key": self._api_key}
        )
        r.raise_for_status()
        parsed = _TmdbCreditsResponse.model_validate(r.json())
        return MovieCreditsResult(id=parsed.id, cast_ids=[c.id for c in parsed.cast])

    async def aclose(self) -> None:
        await self._http.aclose()
