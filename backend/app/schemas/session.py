"""Session state and chat schemas."""

from typing import Literal, Optional
from datetime import date
from pydantic import BaseModel, Field, field_validator, model_validator


class SessionState(BaseModel):
    """Session state — stored in Redis, merged per diff_merge rules."""

    occasion: Optional[str] = None
    category: Optional[str] = None
    color_preference: Optional[str] = None
    budget_max: Optional[int] = None
    style_descriptors: list[str] = Field(default_factory=list)
    size: Optional[str] = None
    deadline_date: Optional[date] = None
    excluded: list[str] = Field(default_factory=list)
    brands: list[str] = Field(default_factory=list)  # empty = all active brands
    department: Optional[str] = None  # 'men' | 'women' | 'unisex' — from onboarding
    wants_kids: bool = False  # shopping for a child — filters TO kids items, not away from them
    child_age_months: Optional[int] = Field(None, ge=0, le=215)
    semantic_query: Optional[str] = None
    excluded_styles: list[str] = Field(default_factory=list)
    fallback_categories: list[str] = Field(default_factory=list)
    fallback_styles: list[str] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    soft_preferences: list[str] = Field(default_factory=list)


IntentOperation = Literal[
    "new_search",
    "refine",
    "replace",
    "remove_filter",
    "show_more",
    "conversation_only",
]

ConstraintField = Literal[
    "occasion",
    "category",
    "color_preference",
    "budget_max",
    "style_descriptors",
    "size",
    "department",
    "child_age_months",
    "brands",
]


class IntentConfidence(BaseModel):
    """LLM confidence for routing and observability, never search content."""

    overall: float = Field(default=0.5, ge=0.0, le=1.0)
    occasion: Optional[float] = Field(None, ge=0.0, le=1.0)
    category: Optional[float] = Field(None, ge=0.0, le=1.0)
    audience: Optional[float] = Field(None, ge=0.0, le=1.0)
    age: Optional[float] = Field(None, ge=0.0, le=1.0)
    operation: Optional[float] = Field(None, ge=0.0, le=1.0)


class IntentExtractionResult(BaseModel):
    """LLM intent extraction result — shape returned by providers."""

    occasion: Optional[str] = None
    category: Optional[str] = None
    color_preference: Optional[str] = None
    budget_max: Optional[int] = None
    style_descriptors: list[str] = Field(default_factory=list)
    size: Optional[str] = None
    urgency_days: Optional[int] = None
    excluded: list[str] = Field(default_factory=list)
    clear_fields: list[str] = Field(
        default_factory=list,
        description="Explicit session filters to remove on this turn.",
    )
    remove_styles: list[str] = Field(
        default_factory=list,
        description="Specific style/material/fit descriptors to remove.",
    )
    excluded_styles: list[str] = Field(
        default_factory=list,
        description="Style/material evidence products must not contain.",
    )
    fallback_categories: list[str] = Field(default_factory=list, max_length=5)
    fallback_styles: list[str] = Field(default_factory=list, max_length=5)
    wants_kids: Optional[bool] = None  # set deterministically in code, not by the LLM — see fast_path_classifier.is_kids_request
    child_age_months: Optional[int] = Field(None, ge=0, le=215)
    department: Optional[str] = Field(
        None,
        pattern="^(men|women)$",
        description="Explicit menswear/womenswear audience stated in this turn.",
    )
    assistant_reply: str = Field(..., description="Generated assistant response")
    clarify: bool = Field(default=False, description="True if clarification needed")
    operation: IntentOperation = "refine"
    semantic_query: str = Field(
        default="",
        description="Standalone normalized description of what the shopper wants.",
    )
    hard_constraints: list[ConstraintField] = Field(default_factory=list)
    soft_preferences: list[ConstraintField] = Field(default_factory=list)
    confidence: IntentConfidence = Field(default_factory=IntentConfidence)

    @field_validator("hard_constraints", "soft_preferences", mode="before")
    @classmethod
    def canonicalize_constraint_fields(cls, value):
        """Repair provider label mistakes without discarding valid intent."""
        if not isinstance(value, list):
            return []
        aliases = {
            "color": "color_preference", "colour": "color_preference",
            "budget": "budget_max", "price": "budget_max",
            "style": "style_descriptors", "material": "style_descriptors",
            "fit": "style_descriptors", "audience": "department",
            "gender": "department", "age": "child_age_months",
            "brand": "brands", "product": "category",
            "product_type": "category",
        }
        allowed = {
            "occasion", "category", "color_preference", "budget_max",
            "style_descriptors", "size", "department", "child_age_months",
            "brands",
        }
        normalized = []
        for item in value:
            key = str(item).strip().lower().replace(" ", "_")
            key = aliases.get(key, key)
            if key in allowed:
                normalized.append(key)
        return normalized

    @model_validator(mode="after")
    def normalize_constraint_roles(self):
        generic_categories = {
            "clothing", "clothes", "apparel", "garment", "garments",
            "outfit", "outfits", "wear",
        }
        if self.category and self.category.strip().lower() in generic_categories:
            self.category = None
            self.hard_constraints = [
                field for field in self.hard_constraints if field != "category"
            ]
            self.soft_preferences = [
                field for field in self.soft_preferences if field != "category"
            ]

        # Visual moods are retrieval descriptors, not literal catalog colours.
        # This is taxonomy validation after semantic extraction—not a user typo
        # dictionary—and prevents impossible filters such as Color: Bright.
        aesthetic_colors = {"bright", "vibrant", "earthy", "neutral"}
        if (
            self.color_preference
            and self.color_preference.strip().lower() in aesthetic_colors
        ):
            mood = self.color_preference.strip().lower()
            self.color_preference = None
            if mood not in self.style_descriptors:
                self.style_descriptors.append(mood)
            if "color_preference" in self.hard_constraints:
                self.hard_constraints = [
                    field for field in self.hard_constraints
                    if field != "color_preference"
                ]
                self.hard_constraints.append("style_descriptors")
            if "color_preference" in self.soft_preferences:
                self.soft_preferences = [
                    field for field in self.soft_preferences
                    if field != "color_preference"
                ]
                self.soft_preferences.append("style_descriptors")

        hard = list(dict.fromkeys(self.hard_constraints))
        hard_keys = set(hard)
        self.hard_constraints = hard
        self.soft_preferences = [
            field for field in dict.fromkeys(self.soft_preferences)
            if field not in hard_keys
        ]
        return self


class ChatTurnRequest(BaseModel):
    """Incoming chat message."""

    query: str = Field(..., min_length=1)
    session_id: Optional[str] = None  # If None, create new session
    department: Optional[str] = None  # set from onboarding, not LLM-extracted
    session_state: Optional[SessionState] = Field(
        None,
        description="Client's last acknowledged state, used only if server state expired.",
    )


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
