"""Protocol for LLM intent extraction providers."""

from typing import Protocol

from app.schemas.session import IntentExtractionResult, SessionState


class IntentExtractionProvider(Protocol):
    """A provider that turns free-text chat input into structured intent."""

    async def extract(
        self, text: str, context: SessionState
    ) -> IntentExtractionResult:
        """Extract structured intent (and a reply) from a user's message.

        Args:
            text: The user's free-text message for this turn.
            context: Current session state, for context-aware extraction
                (e.g. so "cheaper" style follow-ups can reference prior budget).

        Returns:
            Structured diff to merge into session state, plus the assistant's
            reply text and a `clarify` flag when nothing extractable was found.
        """
        ...
