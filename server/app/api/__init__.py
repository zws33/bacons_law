from fastapi import APIRouter

from app.api.movies import router as movies_router
from app.api.people import router as people_router

router = APIRouter()
router.include_router(movies_router)
router.include_router(people_router)
