"""
SQLAlchemy database engine and session factory.
Uses psycopg2 (sync) for Supabase with SSL.
"""
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


def _make_engines():
    settings = get_settings()

    # Sync engine (used for startup checks and migrations)
    sync_engine = create_engine(
        settings.database_url,
        pool_size=3,
        max_overflow=2,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=settings.APP_DEBUG,
    )

    # Async engine (used for API request handlers)
    async_engine = create_async_engine(
        settings.async_database_url,
        pool_size=3,
        max_overflow=2,
        pool_pre_ping=True,
        pool_recycle=1800,
        echo=settings.APP_DEBUG,
    )

    return sync_engine, async_engine


# Module-level singletons
_sync_engine = None
_async_engine = None
_AsyncSessionLocal = None
_SyncSessionLocal = None


def init_db() -> None:
    """Initialize database engines. Called once at application startup."""
    global _sync_engine, _async_engine, _AsyncSessionLocal, _SyncSessionLocal
    _sync_engine, _async_engine = _make_engines()
    _AsyncSessionLocal = async_sessionmaker(
        bind=_async_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    _SyncSessionLocal = sessionmaker(
        bind=_sync_engine,
        autocommit=False,
        autoflush=False,
    )
    logger.info("Database engines initialized.")


async def check_db_connection() -> bool:
    """Verify database connectivity. Returns True if successful."""
    try:
        async with _async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connectivity check: OK")
        return True
    except Exception as exc:
        logger.error("Database connectivity check failed: %s", exc)
        return False


async def check_table_exists(table_name: str) -> bool:
    """Check if a specific table exists in the public schema."""
    try:
        async with _async_engine.connect() as conn:
            result = await conn.execute(
                text(
                    "SELECT EXISTS ("
                    "  SELECT 1 FROM information_schema.tables"
                    "  WHERE table_schema = 'public' AND table_name = :table"
                    ")"
                ),
                {"table": table_name},
            )
            exists: bool = result.scalar()
        return exists
    except Exception as exc:
        logger.error("Table existence check failed for '%s': %s", table_name, exc)
        return False


async def create_pipeline_tables() -> None:
    """
    Create pipeline-specific tables if they don't exist.
    Does NOT touch keam_cutoff_ranks — that table is owned by the Go backend.
    """
    from app.db.models import PipelineBase
    async with _async_engine.begin() as conn:
        await conn.run_sync(PipelineBase.metadata.create_all)
    logger.info("Pipeline tables created/verified.")


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for database sessions."""
    if _AsyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with _AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@contextmanager
def get_sync_session() -> Generator[Session, None, None]:
    """Sync context manager for database sessions (used in tests)."""
    if _SyncSessionLocal is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    session = _SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def dispose_db() -> None:
    """Gracefully close all database connections."""
    if _async_engine:
        await _async_engine.dispose()
    if _sync_engine:
        _sync_engine.dispose()
    logger.info("Database connections disposed.")
