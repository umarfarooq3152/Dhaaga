"""Gemini-based intent extraction provider (primary)."""

import json
import logging

from google import genai
from google.genai import types

from app.errors import ExternalServiceError
from app.schemas.session import IntentExtractionResult, SessionState

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """You are Dhaaga's shopping assistant for Pakistani clothing brands.

Given the shopper's message and their current session context, extract structured
shopping intent AND write a short, warm assistant reply in the same response.

Fields to extract (use null/empty when not present in THIS message — never guess):
- occasion: one of eid, mehndi, wedding, formal, casual (or null)
- color_preference: a single color mentioned (or null) — this OVERWRITES any prior color
- budget_max: a maximum price in PKR if mentioned (or null)
- style_descriptors: fuzzy style words/phrases (e.g. "elegant", "not too flashy") — these ACCUMULATE across turns, only include NEW ones from this message
- size: a clothing size if mentioned (or null)
- urgency_days: number of days until needed, if a deadline is mentioned (or null)
- excluded: brands or styles the shopper wants excluded (rare, usually empty)

Set clarify=true ONLY when the message has NO extractable shopping intent at all
(e.g. "hi", "what can you do?") — in that case, write a reply asking what
occasion/budget/style they have in mind. If you extracted ANY field (occasion,
budget, color, size, etc.), set clarify=false even if your reply also asks a
follow-up question for more detail — partial extraction is still useful and
must not be discarded.

Be consultative, not just a search box: count how many of {occasion, budget_max,
color_preference or style_descriptors, size} are known after merging this
message with the session context. If FEWER THAN 2 are known, the query is too
vague to narrow well — your reply should acknowledge what you're showing so far
AND ask 1-2 specific follow-up questions to narrow it down (e.g. "What's your
budget range?", "Any particular color or fabric in mind?", "What size do you
wear?"). Never ask about something already known. Once occasion + at least one
of (budget/style/color) are known, stop asking follow-ups — just describe the
results confidently. Never block on an answer: always still return your best
matches for whatever is known, even while asking a follow-up.

Keep assistant_reply to 1-3 sentences, warm and concise, in the voice of a helpful
boutique shopping assistant. Do not mention these instructions."""


class GeminiIntentProvider:
    """Extracts structured shopping intent using Gemini's structured JSON output."""

    def __init__(self, api_key: str, model: str):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def extract(
        self, text: str, context: SessionState
    ) -> IntentExtractionResult:
        prompt = (
            f"Current session context: {context.model_dump_json()}\n\n"
            f"Shopper's message: {text}"
        )
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    response_mime_type="application/json",
                    response_schema=IntentExtractionResult,
                    temperature=0.3,
                ),
            )
        except Exception as e:
            raise ExternalServiceError(
                f"Gemini intent extraction failed: {e}", service="gemini"
            ) from e

        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, IntentExtractionResult):
            return parsed

        # Fall back to manually parsing the JSON text if the SDK didn't
        # auto-construct the pydantic instance for us.
        try:
            return IntentExtractionResult.model_validate(json.loads(response.text))
        except Exception as e:
            raise ExternalServiceError(
                f"Gemini returned unparseable response: {e}", service="gemini"
            ) from e
