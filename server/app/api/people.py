from fastapi import APIRouter, Depends

from app.deps import get_tmdb_client
from app.models import PersonSearchResult
from app.tmdb_client import TmdbClient

router = APIRouter(prefix="/people")


@router.get("/search")
async def search_people(
    query: str, tmdb_client: TmdbClient = Depends(get_tmdb_client)
) -> list[PersonSearchResult]:
    return await tmdb_client.search_people(query)
