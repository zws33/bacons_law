from collections.abc import Generator

import fakeredis.aioredis
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store import RoomStore
from app.ws.manager import ConnectionManager
from tests.api.conftest import FakeTmdbClient


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    # Inject fakes directly onto app.state and construct TestClient WITHOUT the
    # context-manager form, so the real lifespan (which opens Redis/TMDB) never runs.
    app.state.tmdb_client = FakeTmdbClient()
    app.state.room_store = RoomStore(fakeredis.aioredis.FakeRedis())
    app.state.connection_manager = ConnectionManager()
    yield TestClient(app)
