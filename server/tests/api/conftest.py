from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.deps import get_tmdb_client
from app.main import app
from app.models import MovieCreditsResult, MovieSearchResult, PersonSearchResult


class FakeTmdbClient:
    async def search_movies(self, query: str) -> list[MovieSearchResult]:
        return [MovieSearchResult(id=550, title="Fight Club", release_year="1999")]

    async def search_people(self, query: str) -> list[PersonSearchResult]:
        return [PersonSearchResult(id=819, name="Brad Pitt")]

    async def get_movie_credits(self, movie_id: int) -> MovieCreditsResult:
        return MovieCreditsResult(id=movie_id, cast_ids=[819, 287])


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_tmdb_client] = lambda: FakeTmdbClient()
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
