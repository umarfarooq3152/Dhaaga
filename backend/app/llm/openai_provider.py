"""OpenAI structured-output intent extraction provider."""

import json
import logging

import httpx

from app.errors import ExternalServiceError
from app.llm.intent_prompt import LLM_FIRST_INTENT_INSTRUCTION
from app.schemas.session import IntentExtractionResult, SessionState

logger = logging.getLogger(__name__)


def _strict_schema() -> dict:
    """Make Pydantic's schema suitable for OpenAI strict JSON outputs."""
    schema = IntentExtractionResult.model_json_schema()

    def visit(node):
        if not isinstance(node, dict):
            return
        if isinstance(node.get("properties"), dict):
            node["required"] = list(node["properties"])
            node["additionalProperties"] = False
            for child in node["properties"].values():
                visit(child)
        for child in node.get("$defs", {}).values():
            visit(child)
        for key in ("items", "anyOf", "oneOf", "allOf"):
            value = node.get(key)
            if isinstance(value, list):
                for child in value:
                    visit(child)
            elif isinstance(value, dict):
                visit(value)

    visit(schema)
    return schema


class OpenAIIntentProvider:
    """Extract intent with OpenAI's Responses-compatible structured JSON API."""

    def __init__(self, api_key: str, model: str, timeout_seconds: float = 8.0):
        self._api_key = api_key
        self._model = model
        self._timeout = timeout_seconds
        self._schema = _strict_schema()

    async def extract(self, text: str, context: SessionState) -> IntentExtractionResult:
        prompt = (
            f"Current session context: {context.model_dump_json()}\n\n"
            f"Shopper's message: {text}"
        )
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": LLM_FIRST_INTENT_INSTRUCTION},
                {"role": "user", "content": prompt},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "dhaaga_intent",
                    "strict": True,
                    "schema": self._schema,
                },
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json=payload,
                )
            if response.status_code >= 400:
                details = {"status_code": response.status_code}
                if response.status_code == 429:
                    details["reason"] = "rate_limited"
                raise ExternalServiceError(
                    f"OpenAI intent extraction failed: {response.text[:500]}",
                    service="openai",
                    details=details,
                )
            body = response.json()
            content = body["choices"][0]["message"].get("content")
            return IntentExtractionResult.model_validate(json.loads(content))
        except ExternalServiceError:
            raise
        except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise ExternalServiceError(
                f"OpenAI intent extraction failed: {error}", service="openai"
            ) from error
