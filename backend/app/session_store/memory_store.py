"""In-memory session store — local dev only, never production.

Single-process, non-persistent: state is lost on restart and isn't shared
across multiple instances. Use RedisSessionStore for anything beyond a
single local dev process.
"""

from app.schemas.product import Product
from app.schemas.session import SessionState


class MemorySessionStore:
    def __init__(self):
        self._states: dict[str, SessionState] = {}
        self._results: dict[str, list[Product]] = {}

    async def get(self, session_id: str) -> SessionState | None:
        return self._states.get(session_id)

    async def set(self, session_id: str, state: SessionState) -> None:
        self._states[session_id] = state

    async def get_last_results(self, session_id: str) -> list[Product]:
        return self._results.get(session_id, [])

    async def set_last_results(self, session_id: str, products: list[Product]) -> None:
        self._results[session_id] = products
