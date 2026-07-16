"""Request and response contracts for the Dhaaga browser extension."""

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExtensionIntent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    category: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=60)
    size: str | None = Field(default=None, max_length=40)
    fit: str | None = Field(default=None, max_length=40)
    price_max: float | None = Field(default=None, alias="priceMax", ge=0)
    price_min: float | None = Field(default=None, alias="priceMin", ge=0)
    descriptive: str | None = Field(default=None, max_length=300)
    occasion: str | None = Field(default=None, max_length=80)
    audience: str | None = Field(default=None, pattern="^(men|women)$")
    wants_kids: bool | None = Field(default=None, alias="wantsKids")
    child_age_months: int | None = Field(
        default=None,
        alias="childAgeMonths",
        ge=0,
        le=215,
    )

    @field_validator("category", "color", "size", "fit", "descriptive", "occasion", "audience", mode="before")
    @classmethod
    def normalize_optional_text(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def has_any_signal(self) -> bool:
        return any(
            (
                self.category,
                self.color,
                self.size,
                self.fit,
                self.price_max is not None,
                self.price_min is not None,
                self.descriptive,
                self.occasion,
                self.audience,
                self.wants_kids is True,
                self.child_age_months is not None,
            )
        )


class ExtensionSearchRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    query: str = Field(..., min_length=1, max_length=500)
    store_origin: str = Field(..., alias="storeOrigin", max_length=300)
    previous_intent: ExtensionIntent | None = Field(default=None, alias="previousIntent")


class ExtensionMatchDetails(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    colors: list[str] = Field(default_factory=list)
    sizes: list[str] = Field(default_factory=list)
    fit: str | None = None
    occasion: str | None = None
    audience: str | None = None
    image_matches_color: bool | None = Field(default=None, alias="imageMatchesColor")


class ExtensionProductResult(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    price: float
    currency: str = "PKR"
    image_url: str = Field(alias="imageUrl")
    product_url: str = Field(alias="productUrl")
    score: float = Field(ge=0, le=10)
    reason: str
    match_details: ExtensionMatchDetails = Field(
        default_factory=ExtensionMatchDetails,
        alias="matchDetails",
    )

class ExtensionSearchMeta(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    store_domain: str = Field(alias="storeDomain")
    fetched_count: int = Field(alias="fetchedCount", ge=0)
    mapped_count: int = Field(default=0, alias="mappedCount", ge=0)
    exact_count: int = Field(default=0, alias="exactCount", ge=0)
    catalog_capped: bool = Field(alias="catalogCapped")
    relaxed: bool = False
    relaxed_filters: list[str] = Field(default_factory=list, alias="relaxedFilters")
    duration_ms: int = Field(alias="durationMs", ge=0)

class ExtensionSearchResponse(BaseModel):
    intent: ExtensionIntent
    products: list[ExtensionProductResult]
    notice: str | None = None
    meta: ExtensionSearchMeta


class CatalogRanking(BaseModel):
    id: str
    score: float = Field(ge=0, le=10)
    reason: str = Field(min_length=1, max_length=180)


class CatalogRankings(BaseModel):
    rankings: list[CatalogRanking] = Field(default_factory=list)
