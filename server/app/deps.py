from fastapi import Request

from app.tmdb_client import TmdbClient


def get_tmdb_client(request: Request) -> TmdbClient:
    client: TmdbClient = request.app.state.tmdb_client
    return client
