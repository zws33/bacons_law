from fastapi import APIRouter, Depends

from app.deps import get_tmdb_client
from app.models import MovieCreditsResult, MovieSearchResult
from app.tmdb_client import TmdbClient

router = APIRouter(prefix="/movies")


@router.get("/search")
async def search_movies(
    query: str, tmdb_client: TmdbClient = Depends(get_tmdb_client)
) -> list[MovieSearchResult]:
    return await tmdb_client.search_movies(query)


@router.get("/{movie_id}/credits")
async def get_credits(
    movie_id: int, tmdb_client: TmdbClient = Depends(get_tmdb_client)
) -> MovieCreditsResult:
    return await tmdb_client.get_movie_credits(movie_id)
