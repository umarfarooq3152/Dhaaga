"""Chat message repository — data access for chat history."""

from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import desc

from app.db.models.chat import ChatMessage


class ChatRepository:
    """Repository for chat_messages table."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_session_history(self, session_id: str, limit: int = 100) -> list[ChatMessage]:
        """Get chat history for a session (most recent first)."""
        result = await self.session.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
        )
        messages = result.scalars().all()
        return list(reversed(messages))  # Return chronologically ordered

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        device_id: Optional[UUID] = None,
    ) -> ChatMessage:
        """Add a message to the chat history."""
        message = ChatMessage(
            session_id=session_id,
            device_id=device_id,
            role=role,
            content=content,
        )
        self.session.add(message)
        # The request router commits once after the complete turn. Flushing
        # every user/assistant message separately adds a remote-Postgres round
        # trip without any caller needing the generated id in between.
        return message

    async def get_session_message_count(self, session_id: str) -> int:
        """Get total message count for a session."""
        result = await self.session.execute(
            select(ChatMessage).where(ChatMessage.session_id == session_id)
        )
        return len(result.scalars().all())
