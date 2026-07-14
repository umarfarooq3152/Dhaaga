# Dhaaga Backend Development Guide

## Local Setup

### Prerequisites

- Python 3.11+
- Redis (local or Docker)
- Postgres 14+ (or Neon test branch)

### Installation

1. **Create virtual environment:**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # or .venv\Scripts\activate on Windows
   ```

2. **Install dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

3. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your local credentials
   ```

4. **Start Redis locally (Docker):**
   ```bash
   docker run -d -p 6379:6379 redis:alpine
   ```

5. **Run migrations:**
   ```bash
   alembic upgrade head
   ```

6. **Start the backend:**
   ```bash
   uvicorn app.main:app --reload
   ```

   Backend runs at `http://localhost:8000`

## Development Workflow

### Running Tests

```bash
# All tests with coverage report
pytest

# Specific test file
pytest tests/unit/nlp/test_keyword_matcher.py -v

# Coverage report (HTML)
pytest --cov-report=html
```

### Formatting & Linting

```bash
# Format code
black app/ tests/

# Check with ruff
ruff check app/ tests/ --fix
```

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Add new table"

# Apply migrations
alembic upgrade head

# Rollback one revision
alembic downgrade -1
```

## Frontend Integration

The frontend expects these environment variables for the backend:

```env
VITE_API_BASE_URL=http://localhost:8000
```

Set this in the frontend's `.env` file.

## Phases & Milestones

See the root implementation plan for phase-by-phase breakdown.
