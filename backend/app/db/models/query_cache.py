"""Query intent cache model — Phase 1."""

from sqlalchemy import String, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone

from app.db.base import Base


class QueryIntentCache(Base):
    """LLM query dedup cache — 24h TTL."""

    __tablename__ = "query_intent_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    query_hash: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    normalized_query: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_intent: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
