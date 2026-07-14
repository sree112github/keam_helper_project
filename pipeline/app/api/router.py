"""
Central API router — aggregates all sub-routers.
"""
from fastapi import APIRouter

from app.api import health, upload, process, preview, insert, settings

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(upload.router)
api_router.include_router(process.router)
api_router.include_router(preview.router)
api_router.include_router(insert.router)
api_router.include_router(settings.router)

