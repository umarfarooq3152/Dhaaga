"""Redis-backed session store — the production backend."""

import json
import logging

import redis.asyncio as redis

from app.schemas.product import Product
from app.schemas.session import SessionState

logger = logging.getLogger(__name__)

STATE_KEY = "session:{session_id}"
RESULTS_KEY = "session:{session_id}:last_results"


class RedisSessionStore:
    """Session state + last-turn results, TTL-bound in Redis."""

    def __init__(self, redis_client: redis.Redis, ttl_hours: int):
        self._redis = redis_client
        self._ttl_seconds = ttl_hours * 3600

    async def get(self, session_id: str) -> SessionState | None:
        raw = await self._redis.get(STATE_KEY.format(session_id=session_id))
        if not raw:
            return None
        try:
            return SessionState.model_validate_json(raw)
        except Exception as e:
            logger.error(f"Failed to deserialize session state for {session_id}: {e}")
            return None

    async def set(self, session_id: str, state: SessionState) -> None:
        await self._redis.setex(
            STATE_KEY.format(session_id=session_id),
            self._ttl_seconds,
            state.model_dump_json(),
        )

    async def get_last_results(self, session_id: str) -> list[Product]:
        raw = await self._redis.get(RESULTS_KEY.format(session_id=session_id))
        if not raw:
            return []
        try:
            return [Product(**p) for p in json.loads(raw)]
        except Exception as e:
            logger.error(f"Failed to deserialize last results for {session_id}: {e}")
            return []

    async def set_last_results(self, session_id: str, products: list[Product]) -> None:
        await self._redis.setex(
            RESULTS_KEY.format(session_id=session_id),
            self._ttl_seconds,
            json.dumps([p.model_dump(mode="json") for p in products]),
        )
