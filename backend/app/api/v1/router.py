from fastapi import APIRouter

from app.api.v1 import trends, topics, scripts, videos

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(trends.router)
api_router.include_router(topics.router)
api_router.include_router(scripts.router)
api_router.include_router(videos.router)
