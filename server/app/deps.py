from fastapi import Request

from app.store import RoomStore
from app.tmdb_client import TmdbClient


def get_tmdb_client(request: Request) -> TmdbClient:
    client: TmdbClient = request.app.state.tmdb_client
    return client


def get_room_store(request: Request) -> RoomStore:
    store: RoomStore = request.app.state.room_store
    return store
