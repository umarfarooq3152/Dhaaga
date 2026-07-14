"""Query cache repository — data access for LLM query dedup."""

from typing import Optional, Any
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models.query_cache import QueryIntentCache
from app.config import get_settings

settings = get_settings()


class QueryCacheRepository:
    """Repository for query_intent_cache table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _hash_query(query: str) -> str:
        """Hash a normalized query for cache key."""
        return sha256(query.lower().strip().encode()).hexdigest()

    async def get_cached(self, normalized_query: str) -> Optional[dict[str, Any]]:
        """Get cached intent extraction for a query (if not expired)."""
        query_hash = self._hash_query(normalized_query)
        result = await self.session.execute(
            select(QueryIntentCache)
            .where(QueryIntentCache.query_hash == query_hash)
            .where(QueryIntentCache.expires_at > datetime.now(timezone.utc))
        )
        cache = result.scalars().first()
        if cache:
            return cache.extracted_intent
        return None

    async def cache_extraction(
        self,
        normalized_query: str,
        extracted_intent: dict[str, Any],
    ) -> None:
        """Cache an intent extraction result.

        Upserts on query_hash rather than a plain INSERT — two near-
        simultaneous requests for the same normalized query (e.g. React
        StrictMode double-invoking an effect, or two users asking the same
        thing) would otherwise collide on the unique constraint and 500.
        """
        query_hash = self._hash_query(normalized_query)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.query_cache_ttl_hours)

        stmt = (
            pg_insert(QueryIntentCache)
            .values(
                query_hash=query_hash,
                normalized_query=normalized_query,
                extracted_intent=extracted_intent,
                expires_at=expires_at,
            )
            .on_conflict_do_update(
                index_elements=["query_hash"],
                set_={"extracted_intent": extracted_intent, "expires_at": expires_at},
            )
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def cleanup_expired(self) -> int:
        """Delete expired cache entries. Returns count of deleted entries."""
        result = await self.session.execute(
            select(QueryIntentCache).where(
                QueryIntentCache.expires_at <= datetime.now(timezone.utc)
            )
        )
        entries = result.scalars().all()
        for entry in entries:
            await self.session.delete(entry)
        await self.session.flush()
        return len(entries)
