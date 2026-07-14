# Neon Postgres Setup for Dhaaga

## Create a New Neon Project

1. **Navigate to Neon Console:** https://console.neon.tech/

2. **Create a new project:**
   - Project name: `dhaaga`
   - Organization: `Umar` (org_id: `org-noisy-wildflower-51804812`)
   - Region: Choose closest to your deployment region
   - Database: `dhaaga` (auto-created)

3. **Get Connection String:**
   - Copy the `postgres://...` connection string from the project's "Connection String" section
   - Replace with `postgresql+asyncpg://...` for SQLAlchemy async driver

## Connection URL Format

For Railway backend:
```
postgresql+asyncpg://user:password@ep-noisy-project.region.aws.neon.tech/dhaaga?sslmode=require
```

## First Run

After setting `DATABASE_URL` in `.env`:

```bash
cd backend
python -m alembic upgrade head
```

This runs all migrations and creates the schema.

## Important Notes

- **DO NOT modify** existing Neon projects (`Retailop` or `ancient-brook-12017928`)
- **pgvector extension is NOT needed** — plain Postgres is sufficient for this MVP
- Neon's free tier includes branching for development — use a dev branch for testing migrations
- Connection pooling via Neon's built-in pooler is recommended for Railway
