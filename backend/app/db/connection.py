"""Database connection and session management."""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

# Global engine and session factory
_engine = None
_async_session_maker = None


async def init_db():
    """Initialize database connection."""
    global _engine, _async_session_maker

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

    _async_session_maker = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    logger.info("Database connection initialized")


async def close_db():
    """Close database connection."""
    global _engine

    if _engine:
        await _engine.dispose()
        logger.info("Database connection closed")


def get_session_maker():
    """Get session maker factory."""
    if not _async_session_maker:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _async_session_maker


async def get_session() -> AsyncSession:
    """Dependency for FastAPI — get async session."""
    maker = get_session_maker()
    async with maker() as session:
        yield session
