"""Session event repository — data access for analytics."""

from typing import Optional, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models.events import SessionEvent


class SessionEventRepository:
    """Repository for session_events table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def log_event(
        self,
        session_id: str,
        event_type: str,
        device_id: Optional[UUID] = None,
        product_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> SessionEvent:
        """Log an analytics event."""
        event = SessionEvent(
            session_id=session_id,
            device_id=device_id,
            event_type=event_type,
            product_id=product_id,
            event_metadata=metadata or {},
        )
        self.session.add(event)
        # Batched into the request's final transaction commit; no caller needs
        # the generated event id during intent extraction or search.
        return event

    async def get_session_events(self, session_id: str, event_type: Optional[str] = None) -> list[SessionEvent]:
        """Get events for a session, optionally filtered by type."""
        query = select(SessionEvent).where(SessionEvent.session_id == session_id)
        if event_type:
            query = query.where(SessionEvent.event_type == event_type)
        result = await self.session.execute(query.order_by(SessionEvent.created_at))
        return result.scalars().all()

    async def count_turns_to_first_click(self, session_id: str) -> Optional[int]:
        """Get number of turns before first product_click in session."""
        events = await self.get_session_events(session_id)
        turn_count = 0
        for event in events:
            if event.event_type == "product_click":
                return turn_count
            if event.event_type in ("turn_fast_path", "turn_llm_extraction"):
                turn_count += 1
        return None  # No click in this session
