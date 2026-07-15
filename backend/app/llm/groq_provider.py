"""Groq-based intent extraction provider (fallback when Gemini is unavailable)."""

import json
import logging

from groq import AsyncGroq

from app.errors import ExternalServiceError
from app.schemas.session import IntentExtractionResult, SessionState

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """You are Dhaaga's shopping assistant for Pakistani clothing brands.
Respond ONLY with a single JSON object (no prose, no markdown fences) matching this shape:

{
  "occasion": "eid" | "mehndi" | "wedding" | "formal" | "casual" | null,
  "color_preference": string | null,
  "budget_max": number | null,
  "style_descriptors": string[],
  "size": string | null,
  "urgency_days": number | null,
  "excluded": string[],
  "assistant_reply": string,
  "clarify": boolean
}

Rules:
- Only include fields explicitly present in THIS message — use null/empty, never guess.
- style_descriptors and excluded should only contain NEW items from this message (the
  caller accumulates them across turns); color_preference and budget_max overwrite.
- Set clarify=true ONLY when NO field could be extracted at all (e.g. "hi") — in
  that case assistant_reply should ask what occasion/budget/style the shopper
  has in mind. If you extracted ANY field, set clarify=false even if your reply
  also asks a follow-up question — partial extraction is still useful and must
  not be discarded.
- Be consultative, not just a search box: count how many of {occasion,
  budget_max, color_preference or style_descriptors, size} are known after
  merging this message with the session context. If FEWER THAN 2 are known,
  the query is too vague to narrow well — assistant_reply should acknowledge
  what you're showing so far AND ask 1-2 specific follow-up questions (e.g.
  "What's your budget range?", "Any particular color or fabric in mind?",
  "What size do you wear?"). Never ask about something already known. Once
  occasion + at least one of (budget/style/color) are known, stop asking
  follow-ups — just describe the results confidently. Never block on an
  answer: always still return your best matches for whatever is known, even
  while asking a follow-up.
- assistant_reply: 1-3 warm, concise sentences as a boutique shopping assistant."""


class GroqIntentProvider:
    """Extracts structured shopping intent using Groq's JSON mode (fallback path)."""

    def __init__(self, api_key: str, model: str):
        self._client = AsyncGroq(api_key=api_key)
        self._model = model

    async def extract(
        self, text: str, context: SessionState
    ) -> IntentExtractionResult:
        user_prompt = (
            f"Current session context (JSON): {context.model_dump_json()}\n\n"
            f"Shopper's message: {text}"
        )
        messages = [
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": user_prompt},
        ]

        raw = await self._complete(messages)
        try:
            return IntentExtractionResult.model_validate(json.loads(raw))
        except Exception as first_error:
            logger.warning(f"Groq response failed validation, retrying once: {first_error}")
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": (
                    "That wasn't valid JSON matching the required shape. "
                    f"Validation error: {first_error}. Reply with ONLY the corrected JSON object."
                ),
            })
            raw_retry = await self._complete(messages)
            try:
                return IntentExtractionResult.model_validate(json.loads(raw_retry))
            except Exception as second_error:
                raise ExternalServiceError(
                    f"Groq returned an unparseable/invalid response after retry: {second_error}",
                    service="groq",
                ) from second_error

    async def _complete(self, messages: list[dict]) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            return response.choices[0].message.content
        except Exception as e:
            raise ExternalServiceError(
                f"Groq intent extraction failed: {e}", service="groq"
            ) from e
