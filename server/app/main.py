import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx2
from fastapi import FastAPI

from app.api import router
from app.tmdb_client import HttpxTmdbClient


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    api_key = os.environ["TMDB_API_KEY"]
    tmdb = HttpxTmdbClient(api_key=api_key, http_client=httpx2.AsyncClient())
    app.state.tmdb_client = tmdb
    yield
    await tmdb.aclose()


app = FastAPI(lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
