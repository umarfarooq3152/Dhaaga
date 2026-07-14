# Dhaaga Backend — Comprehensive Implementation Plan

## Overview

Dhaaga is a conversational search backend for Pakistani clothing brands. This is a **live-fetch-with-cache** MVP that avoids building a persistent product database.

**Key insight:** Products are fetched live from Shopify storefronts, cached in Redis for 20-30 minutes, and searched via keyword matching (no embeddings). This eliminates the need for ingestion pipelines, crawl state tracking, and pgvector — making the backend lean and fast.

## Architecture Principles

1. **No persistent product DB** — Shopify storefronts are the source of truth
2. **Live-fetch + cache** — Brief Redis cache (20-30 min TTL) with proactive refresh
3. **Tier-1 only** — 16 Shopify-based brands, no complex scraping
4. **Keyword-based search** — Fuzzy substring matching over product metadata
5. **Lightweight LLM integration** — Gemini (primary) → Groq (fallback) for intent extraction
6. **Session-scoped state** — Redis-backed session store, no persistent conversation history required

## File Structure

```
backend/
├── pyproject.toml                   # Dependencies + build config
├── alembic.ini                      # Migration config
├── .env.example                     # Environment template
├── migrations/env.py                # Alembic environment
├── migrations/versions/             # Migration scripts (auto-generated)
├── app/
│   ├── main.py                      # FastAPI app factory + routes
│   ├── config.py                    # Pydantic settings (env-driven)
│   ├── errors.py                    # Exception hierarchy
│   ├── db/models/
│   │   ├── brand.py
│   │   ├── device.py
│   │   ├── wishlist.py
│   │   ├── chat.py
│   │   ├── collections.py
│   │   └── base.py                  # SQLAlchemy declarative base
│   ├── repositories/                # Data access layer
│   │   ├── brand_repo.py
│   │   ├── device_repo.py
│   │   ├── wishlist_repo.py
│   │   ├── chat_repo.py
│   │   ├── query_cache_repo.py
│   │   └── collections_repo.py
│   ├── schemas/                     # Pydantic request/response DTOs
│   │   ├── product.py
│   │   ├── brand.py
│   │   ├── session.py
│   │   ├── chat.py
│   │   └── device.py
│   ├── services/
│   │   ├── product_cache_service.py # Core: Redis-backed live cache
│   │   ├── search_service.py        # Structured filters + keyword scoring
│   │   ├── alternatives_service.py  # Tag/category overlap
│   │   ├── collections_service.py   # Curated filter resolution
│   │   ├── session_service.py       # Redis session state store
│   │   ├── intent_service.py        # LLM intent extraction orchestration
│   │   └── wishlist_service.py      # Wishlist CRUD
│   ├── llm/
│   │   ├── provider.py              # Protocol base class
│   │   ├── gemini_provider.py       # Gemini implementation
│   │   ├── groq_provider.py         # Groq implementation
│   │   └── fallback.py              # Fallback orchestration
│   ├── nlp/
│   │   ├── fast_path_classifier.py  # Deterministic keyword matching
│   │   ├── query_normalizer.py      # Input normalization
│   │   ├── diff_merge.py            # SessionState merging logic
│   │   └── keyword_matcher.py       # Fuzzy substring scoring
│   ├── session_store/
│   │   ├── base.py                  # Protocol for session storage
│   │   ├── redis_store.py           # Redis implementation
│   │   └── memory_store.py          # In-memory (dev-only)
│   ├── shopify/
│   │   ├── client.py                # Shopify /products.json paginated fetch
│   │   └── mapper.py                # JSON → Product normalization
│   └── routers/
│       ├── devices.py               # POST /devices, PATCH /devices/{id}
│       ├── wishlist.py              # GET/POST/DELETE /wishlist/*
│       ├── products.py              # GET /products/search, /products/{id}, /products/{id}/alternatives
│       ├── brands.py                # GET /brands
│       ├── collections.py           # GET /collections*
│       ├── session.py               # POST /session/message
│       └── health.py                # GET /healthz
├── seed/
│   ├── brands_seed.json             # 16 brands registry
│   ├── seed_brands.py               # Brands seeding script
│   ├── collections_seed.json        # Curated collections
│   └── seed_collections.py          # Collections seeding script
└── tests/
    ├── conftest.py                  # pytest fixtures
    ├── unit/
    │   ├── nlp/
    │   │   ├── test_keyword_matcher.py
    │   │   ├── test_fast_path_classifier.py
    │   │   └── test_diff_merge.py
    │   ├── shopify/
    │   │   └── test_mapper.py
    │   ├── services/
    │   │   ├── test_search_service.py
    │   │   └── test_alternatives_service.py
    │   └── llm/
    │       └── test_fallback.py
    ├── integration/
    │   ├── test_product_cache.py
    │   ├── test_session_api.py
    │   └── test_wishlist_api.py
    └── e2e/
        └── test_full_journey.py
```

## API Surface (Quick Reference)

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/devices` | Issue anonymous device_id |
| PATCH | `/devices/{id}` | Persist device size |
| GET | `/wishlist` | Hydrated wishlist items |
| POST | `/wishlist/{product_id}` | Add to wishlist |
| DELETE | `/wishlist/{product_id}` | Remove from wishlist |
| GET | `/products/search` | Query with filters (occasion, budget, size, color, etc.) |
| GET | `/products/{id}` | Fetch single product |
| GET | `/products/{id}/alternatives` | Tag-scored alternatives |
| GET | `/collections` | Curated tiles metadata |
| GET | `/collections/{id}/products` | Resolve collection filter live |
| GET | `/brands` | All 16 brands |
| POST | `/session/message` | Chat turn → intent extraction → search → response |
| GET | `/healthz` | DB + Redis check |

## Core Concepts

### Product Identity

```
"{brand_slug}:{shopify_product_id}"
```

E.g. `"limelight:8439992975448"` — deterministic, no DB row needed.

### Session State

Stored in Redis, TTL 6 hours. Merges per the diff-merge rules:

```python
class SessionState(BaseModel):
    occasion: Optional[str] = None
    color_preference: Optional[str] = None
    budget_max: Optional[int] = None
    style_descriptors: List[str] = []
    size: Optional[str] = None
    deadline_date: Optional[date] = None
    excluded: List[str] = []
    brands: List[str] = []  # empty = all 16
```

### Intent Extraction Result

LLM returns structured JSON:

```python
class IntentExtractionResult(BaseModel):
    occasion: Optional[str]
    color_preference: Optional[str]
    budget_max: Optional[int]
    style_descriptors: List[str]
    size: Optional[str]
    urgency_days: Optional[int]
    excluded: List[str]
    assistant_reply: str
    clarify: bool
```

**Merging rule (simplified):**

- If `occasion` changes (topic shift) → clear `deadline_date`
- `style_descriptors` and `excluded` are accumulated (no deduplicate within a turn)
- All other fields overwrite if present in diff

### Product Cache

**Key:** `products:{brand_slug}`
**Value:** Serialized `List[Product]`
**TTL:** 30 minutes

**Refresh strategy:**
- Every 20 minutes, background job calls `get_brand_products(slug)` for each of 16 brands
- If cache is fresh → skip
- If cache is stale/missing → fetch from `https://{domain}/products.json?limit=250&since_id=...`
- On error: log, continue (per-brand isolation)
- Redis operation is atomic (get + set with lock to prevent thundering herd)

### Shopify Product Mapping

```python
class Product(BaseModel):
    id: str                  # "{brand_slug}:{shopify_id}"
    name: str
    description: Optional[str]
    price: float             # Min variant price
    colors: List[str]        # Dedup variant Color/Colour options
    sizes: List[str]         # Dedup variant Size options
    occasion: Optional[str]  # From keyword tagging (mehndi, barat, eid, formal, casual...)
    tags: List[str]          # From keyword tagging (silk, lawn, chiffon, embroidery...)
    image: str               # First image URL
    secondaryImage: Optional[str]  # Second image URL
    product_url: str         # Shopify product page
```

**Tagging logic (rule-based keyword matching):**

- Match name/description/tags/product_type against known occasion keywords (mehndi/barat/eid/formal/casual)
- Match against material keywords (silk/lawn/chiffon/velvet/cotton/embroidery/etc.)
- No match + thin description → `occasion=None`, `tags=['unclassified']`

## Database Schema (Postgres)

See the plan document for full schema SQL. Key tables:

- `brand_registry` — 16 rows, one per brand
- `devices` — anonymous session tracking
- `wishlist_items` — device_id + composite product_id (no FK)
- `chat_messages` — durable log (real-time state is in Redis)
- `session_events` — analytics (turns-to-click)
- `query_intent_cache` — LLM query dedup (24h TTL)
- `collections` — curated filter definitions

## Phase-by-Phase Breakdown

### Phase 0: Groundwork ✓
- Git init, backend skeleton, pyproject.toml, config, Neon project setup

### Phase 1: Schema + Seed
- Alembic migration (7 tables)
- Seed 16 brands + collections
- Repository layer

### Phase 2: Live Fetch + Cache
- Shopify client/mapper
- Keyword theme tagger
- `product_cache_service.py` + background job

### Phase 3: Search API
- Structured filters + keyword scoring
- Alternatives endpoint
- Wishlist CRUD
- Collections resolution

### Phase 4: LLM + Session Engine
- Provider abstraction
- Fast-path classifier
- Diff-merge logic
- Session orchestration

### Phase 5: Frontend Integration
- Hooks (useDeviceId, useWishlist, useSessionChat)
- Component rewiring
- Playwright E2E

### Phase 6: Deploy + Hardening
- Railway/Vercel cutover
- Rate limiting
- Structured logging
- Production verification

## Testing Strategy

**80% coverage target** — realistic enforcement:

- **Unit**: `nlp/` modules (keyword matcher, fast-path classifier, diff-merge), `shopify/mapper.py`, search/alternatives scoring
- **Integration**: `product_cache_service.py` (cache hit/miss/stale/refresh behavior), wishlist CRUD, session API with fake LLM
- **E2E**: One full journey (skip onboarding → search → chat → product detail → wishlist) with fake LLM

## Environment Variables

```
# Database
DATABASE_URL=postgresql+asyncpg://...

# LLM
GEMINI_API_KEY=...
GROQ_API_KEY=...

# Cache
REDIS_URL=redis://...

# Frontend
FRONTEND_ORIGIN=http://localhost:5173

# Config
ENVIRONMENT=development
SESSION_STORE_BACKEND=redis
LOG_LEVEL=info
```

## Deployment

- **Backend**: Railway (FastAPI + Redis add-on, alembic upgrade head in release hook)
- **Frontend**: Vercel (unchanged, VITE_API_BASE_URL → Railway domain)
- **Database**: Neon project `dhaaga`
- **Rate limiting**: 20/min `/session/message` per device, 60/min elsewhere per IP

---

## Next Steps

1. **Create Neon project** `dhaaga` under org `Umar`
2. **Set up local environment** and run initial migration
3. **Implement Phase 1** (schema + seed)

See [BACKEND_DEV_GUIDE.md](./BACKEND_DEV_GUIDE.md) for step-by-step setup.
