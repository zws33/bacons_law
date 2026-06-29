import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx2
import redis.asyncio as redis
from fastapi import FastAPI

from app.api import router as api_router
from app.store import RoomStore
from app.tmdb_client import HttpxTmdbClient
from app.ws import router as ws_router
from app.ws.manager import ConnectionManager


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    tmdb = HttpxTmdbClient(api_key=os.environ["TMDB_API_KEY"], http_client=httpx2.AsyncClient())
    redis_client = redis.Redis.from_url(os.environ["REDIS_URL"])

    app.state.tmdb_client = tmdb
    app.state.room_store = RoomStore(redis_client)
    app.state.connection_manager = ConnectionManager()

    yield

    await tmdb.aclose()
    await redis_client.aclose()


app = FastAPI(lifespan=lifespan)
app.include_router(api_router)
app.include_router(ws_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
