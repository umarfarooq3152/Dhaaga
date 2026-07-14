# Dhaaga Backend

FastAPI backend for conversational search over Pakistani clothing brands.

**Status:** Phase 0 Groundwork Complete

## Quick Start

### 1. Set up environment

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

### 2. Configure `.env`

Get credentials for:
- `DATABASE_URL` from Neon (see [docs/NEON_SETUP.md](../docs/NEON_SETUP.md))
- `GEMINI_API_KEY` and `GROQ_API_KEY` from respective services
- `REDIS_URL` from local Docker or Railway

### 3. Run migrations

```bash
alembic upgrade head
```

### 4. Start backend

```bash
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`

## Testing

```bash
# Run all tests with coverage
pytest

# Specific test file
pytest tests/unit/nlp/test_keyword_matcher.py -v

# HTML coverage report
pytest --cov-report=html
```

## Documentation

- [BACKEND_OVERVIEW.md](../docs/BACKEND_OVERVIEW.md) — Architecture & file structure
- [BACKEND_DEV_GUIDE.md](../docs/BACKEND_DEV_GUIDE.md) — Development setup & workflow
- [NEON_SETUP.md](../docs/NEON_SETUP.md) — Neon Postgres configuration
- [PHASE0_COMPLETE.md](../docs/PHASE0_COMPLETE.md) — What's ready, what's next

## Implementation Plan

See the root directory's implementation plan for the full 6-phase breakdown.

## Project Structure

```
app/
├── main.py              # FastAPI app factory
├── config.py            # Environment configuration
├── errors.py            # Exception hierarchy
├── db/models/           # SQLAlchemy ORM models
├── repositories/        # Data access layer
├── schemas/             # Pydantic DTOs
├── services/            # Business logic
├── llm/                 # LLM providers (Gemini, Groq)
├── nlp/                 # NLP utilities
├── session_store/       # Session state backends
├── shopify/             # Shopify API integration
└── routers/             # API endpoints
```

## Next Phase (Phase 1)

- Implement 7-table Alembic migration
- Seed 16 brands + collections
- Build repository layer for CRUD operations

See [PHASE0_COMPLETE.md](../docs/PHASE0_COMPLETE.md) for detailed next steps.
