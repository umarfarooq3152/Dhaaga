"""Protocol for session state storage backends."""

from typing import Protocol

from app.schemas.product import Product
from app.schemas.session import SessionState


class SessionStore(Protocol):
    """Stores live, session-scoped chat state — never the durable chat log
    (that's `chat_messages` in Postgres, written by ChatRepository)."""

    async def get(self, session_id: str) -> SessionState | None:
        """Return the current session state, or None if missing/expired."""
        ...

    async def set(self, session_id: str, state: SessionState) -> None:
        """Persist session state, resetting its TTL."""
        ...

    async def get_last_results(self, session_id: str) -> list[Product]:
        """Return the products shown in the previous turn (empty if none)."""
        ...

    async def set_last_results(self, session_id: str, products: list[Product]) -> None:
        """Persist the products shown in this turn, for fast-path refinements."""
        ...
