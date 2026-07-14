# Phase 0: Groundwork Complete ✓

Backend skeleton is now ready. Follow these steps to get started:

## 1. Create Neon Project

See [NEON_SETUP.md](./NEON_SETUP.md) for detailed instructions.

**Quick summary:**
- Create project named `dhaaga` under org `Umar`
- Copy `postgresql+asyncpg://...` connection string to `backend/.env`

## 2. Set Up Local Environment

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edit .env with real values
```

## 3. Start Redis Locally

```bash
docker run -d -p 6379:6379 redis:alpine
```

## 4. Run Initial Migration

```bash
alembic upgrade head
```

## 5. Start Backend

```bash
uvicorn app.main:app --reload
```

Test with:
```bash
curl http://localhost:8000/healthz
```

Should return:
```json
{"status": "ok", "environment": "development"}
```

---

## Next: Phase 1 (Schema + Seed)

Ready to implement:
- 7-table schema (brand_registry, devices, wishlist_items, chat_messages, session_events, query_intent_cache, collections)
- Seed 16 brands + sample collections
- Repository layer for DB access
