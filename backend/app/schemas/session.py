"""Session state and chat schemas."""

from typing import Optional
from datetime import date
from pydantic import BaseModel, Field


class SessionState(BaseModel):
    """Session state — stored in Redis, merged per diff_merge rules."""

    occasion: Optional[str] = None
    color_preference: Optional[str] = None
    budget_max: Optional[int] = None
    style_descriptors: list[str] = Field(default_factory=list)
    size: Optional[str] = None
    deadline_date: Optional[date] = None
    excluded: list[str] = Field(default_factory=list)
    brands: list[str] = Field(default_factory=list)  # empty = all active brands
    department: Optional[str] = None  # 'men' | 'women' | 'unisex' — from onboarding
    wants_kids: bool = False  # shopping for a child — filters TO kids items, not away from them


class IntentExtractionResult(BaseModel):
    """LLM intent extraction result — shape returned by providers."""

    occasion: Optional[str] = None
    color_preference: Optional[str] = None
    budget_max: Optional[int] = None
    style_descriptors: list[str] = Field(default_factory=list)
    size: Optional[str] = None
    urgency_days: Optional[int] = None
    excluded: list[str] = Field(default_factory=list)
    wants_kids: Optional[bool] = None  # set deterministically in code, not by the LLM — see fast_path_classifier.is_kids_request
    assistant_reply: str = Field(..., description="Generated assistant response")
    clarify: bool = Field(default=False, description="True if clarification needed")


class ChatTurnRequest(BaseModel):
    """Incoming chat message."""

    query: str = Field(..., min_length=1)
    session_id: Optional[str] = None  # If None, create new session
    department: Optional[str] = None  # set from onboarding, not LLM-extracted


class SessionResetRequest(BaseModel):
    """Clear a session's filters/state back to fresh — used by "Clear All"."""

    session_id: str


class ChatTurnResponse(BaseModel):
    """Chat turn response — includes session state, search results, reply."""

    session_id: str
    reply: str
    session_state: SessionState
    filters: dict = Field(default_factory=dict, description="User-friendly filter descriptions")
    products: "ProductSearchResponse" = Field(description="Search results")
    turn_type: str = Field(description="fast_path or llm_extraction")

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "uuid-string",
                "reply": "I found 14 pieces under Rs. 30,000...",
                "session_state": {
                    "occasion": "Eid",
                    "budget_max": 30000,
                    "style_descriptors": ["elegant"],
                },
                "filters": {
                    "occasion": "Eid",
                    "budget": "Under Rs. 30,000",
                },
                "products": {
                    "items": [],
                    "total": 14,
                    "page": 1,
                    "page_size": 20,
                    "has_more": False,
                },
                "turn_type": "llm_extraction",
            }
        }


# Import at end to avoid circular imports
from app.schemas.product import ProductSearchResponse  # noqa: E402

ChatTurnResponse.model_rebuild()
