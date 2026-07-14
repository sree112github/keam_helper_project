"""
FastAPI dependency injection providers.
"""
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db.database import get_async_session


async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async database session for a request."""
    async with get_async_session() as session:
        yield session


def settings_dep() -> Settings:
    """Provide application settings."""
    return get_settings()
