"""
FastAPI application factory and global setup.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import text

from app.config import get_settings
from app.db.connection import init_db, close_db, get_session_maker
from app.errors import DhaagaException
from app.repositories.brand_repo import BrandRepository
from app.services.product_cache_service import (
    create_cache_service,
    close_cache_service,
    ProductCacheService,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# Global rate limiter
limiter = Limiter(key_func=get_remote_address)

# Global cache service (initialized on startup)
_cache_service: ProductCacheService | None = None
_scheduler: AsyncIOScheduler | None = None


async def get_cache_service() -> ProductCacheService:
    """Get or create cache service instance."""
    global _cache_service
    if _cache_service is None:
        _cache_service = await create_cache_service()
    return _cache_service


async def refresh_products_job():
    """Background job to refresh all brand products every 20 minutes."""
    try:
        logger.info("Starting product refresh job")
        cache_service = await get_cache_service()
        session_maker = get_session_maker()

        # Get all active brands
        async with session_maker() as session:
            brand_repo = BrandRepository(session)
            brands = await brand_repo.get_all_active()

        # Refresh each brand
        if brands:
            brands_data = [{"slug": b.slug, "domain": b.domain} for b in brands]
            results = await cache_service.refresh_all_brands(brands_data)
            logger.info(f"Product refresh job complete: {results}")
        else:
            logger.warning("No active brands found for refresh")
    except Exception as e:
        logger.error(f"Product refresh job failed: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    logger.info("🚀 Dhaaga backend starting")
    await init_db()

    # Initialize cache service and background scheduler
    cache_service = await get_cache_service()
    logger.info("✓ Product cache service initialized")

    # Setup background job for product refresh
    global _scheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        refresh_products_job,
        "interval",
        minutes=20,
        id="refresh_products",
        name="Refresh all brand products",
        max_instances=1,  # Prevent concurrent runs
    )
    _scheduler.start()
    logger.info("✓ Background scheduler started (refresh every 20 min)")

    yield

    # Shutdown
    if _scheduler:
        _scheduler.shutdown()
        logger.info("✓ Background scheduler stopped")

    if cache_service:
        await close_cache_service(cache_service)
        logger.info("✓ Cache service closed")

    await close_db()
    logger.info("🛑 Dhaaga backend shutting down")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="Dhaaga",
        description="Conversational search backend for Pakistani clothing brands",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*", "X-Device-Id"],
    )

    # Add rate limiter
    app.state.limiter = limiter

    # Exception handlers
    @app.exception_handler(DhaagaException)
    async def dhaaga_exception_handler(request: Request, exc: DhaagaException):
        """Handle Dhaaga exceptions."""
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle unexpected exceptions."""
        logger.exception("Unhandled exception", extra={"path": request.url.path})
        if settings.debug:
            raise
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An unexpected error occurred",
                }
            },
        )

    # Health check endpoint
    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        """Health check — verifies DB and Redis connectivity."""
        from redis.asyncio import from_url as redis_from_url

        health_status = {"status": "ok", "environment": settings.environment}

        # Check database
        try:
            session_maker = get_session_maker()
            async with session_maker() as session:
                await session.execute(text("SELECT 1"))
            health_status["database"] = "ok"
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            health_status["database"] = f"error: {str(e)}"
            health_status["status"] = "degraded"

        # Check Redis
        try:
            redis_client = await redis_from_url(settings.redis_url)
            await redis_client.ping()
            await redis_client.close()
            health_status["cache"] = "ok"
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            health_status["cache"] = f"error: {str(e)}"
            health_status["status"] = "degraded"

        return health_status

    # Register routers
    from app.routers import products, devices, brands, wishlist, collections, session

    app.include_router(products.router)
    app.include_router(devices.router)
    app.include_router(brands.router)
    app.include_router(wishlist.router)
    app.include_router(collections.router)
    app.include_router(session.router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
