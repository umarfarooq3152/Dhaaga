"""Session/chat API router — the core conversational search endpoint."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.connection import get_session
from app.llm.fallback import FallbackIntentProvider
from app.llm.gemini_provider import GeminiIntentProvider
from app.llm.groq_provider import GroqIntentProvider
from app.repositories.brand_repo import BrandRepository
from app.repositories.chat_repo import ChatRepository
from app.repositories.events_repo import SessionEventRepository
from app.repositories.query_cache_repo import QueryCacheRepository
from app.schemas.session import ChatTurnRequest, ChatTurnResponse, SessionResetRequest
from app.services.product_cache_service import ProductCacheService, create_cache_service
from app.services.session_service import SessionService
from app.session_store.redis_store import RedisSessionStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/session", tags=["session"])

# Providers are stateless HTTP clients — safe to build once and reuse.
_settings = get_settings()
_fallback_provider = FallbackIntentProvider(
    primary=GeminiIntentProvider(_settings.gemini_api_key, _settings.gemini_model),
    fallback=GroqIntentProvider(_settings.groq_api_key, _settings.groq_model),
    primary_timeout_seconds=_settings.gemini_timeout_seconds,
    fallback_timeout_seconds=_settings.groq_timeout_seconds,
)


async def get_session_service(
    db_session: AsyncSession = Depends(get_session),
    cache_service: ProductCacheService = Depends(create_cache_service),
) -> SessionService:
    """Build a SessionService with a fresh Redis connection for this request."""
    import redis.asyncio as redis

    redis_client = redis.from_url(_settings.redis_url)
    session_store = RedisSessionStore(redis_client, ttl_hours=_settings.session_ttl_hours)

    return SessionService(
        session_store=session_store,
        fallback_provider=_fallback_provider,
        chat_repo=ChatRepository(db_session),
        events_repo=SessionEventRepository(db_session),
        query_cache_repo=QueryCacheRepository(db_session),
        brand_repo=BrandRepository(db_session),
        cache_service=cache_service,
    )


@router.post("/message", response_model=ChatTurnResponse)
async def send_message(
    payload: ChatTurnRequest,
    device_id: Optional[UUID] = Header(None, alias="X-Device-Id"),
    db_session: AsyncSession = Depends(get_session),
    service: SessionService = Depends(get_session_service),
) -> ChatTurnResponse:
    """Send a chat turn: text in, structured intent extraction + search out.

    X-Device-Id is optional — chat works anonymously; when present, messages
    are attributed to that device for the chat log and analytics events.
    """
    try:
        result = await service.handle_turn(
            session_id=payload.session_id,
            device_id=device_id,
            text=payload.query,
        )
        await db_session.commit()
        return result
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Session message failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process message")


@router.post("/reset", response_model=ChatTurnResponse)
async def reset_session(
    payload: SessionResetRequest,
    db_session: AsyncSession = Depends(get_session),
    service: SessionService = Depends(get_session_service),
) -> ChatTurnResponse:
    """Clear a session's filters/state back to fresh — backs the "Clear All" action."""
    try:
        result = await service.reset_session(payload.session_id)
        await db_session.commit()
        return result
    except Exception as e:
        await db_session.rollback()
        logger.error(f"Session reset failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to reset session")
