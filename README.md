# Dhaaga

A conversational shopping assistant for Pakistani fashion. Describe what you're looking for in plain language — "an elegant Eid outfit under Rs. 30,000" — and Dhaaga searches live across multiple real Pakistani clothing brands, refines results turn by turn, and links out to the brand's own store to complete the purchase. Dhaaga is an aggregator, not a marketplace: it never handles checkout, and every product links back to the brand that sells it.

## Features

- **Hybrid live search, no product database.** A Redis index refreshed from each brand's public Shopify catalog quickly produces a bounded relevant shortlist. Before a card reaches the UI, Dhaaga calls that product's live Shopify endpoint, drops sold-out/deleted listings, updates current price and available variants, and reapplies every hard filter — the brand's store remains the source of truth.
- **Conversational, LLM-first intent.** Gemini extracts typed shopping intent, with Groq as an automatic fallback. Deterministic logic handles session controls and validates strict facts such as audience, child age, size, and budget. Intent diffs merge into session state so shoppers can naturally say "blue instead", "under 10,000", or "show more".
- **Exact-first recommendations with staged relaxation.** Audience, adult/child scope, exact child age, availability and explicit negative exclusions remain hard boundaries. Exact matches lead; sparse result sets are then filled with relevance-ranked near-matches by relaxing soft style, occasion, dressiness, color, size or budget one field at a time.
- **Data-quality filtering at ingestion.** Real Pakistani fashion brands sell more than clothes through the same Shopify store — home textiles, perfume, jewelry, fabric sold by the meter. Anything that isn't a wearable garment, is implausibly priced, or has no product image is excluded when a brand's catalog is fetched.
- **Voice search** via Groq Whisper transcription, both in the web app and the Chrome extension.
- Curated editorial collections, a wishlist, device-based sessions, and a Menswear/Womenswear department preference set at onboarding.
- **Chrome extension MVP** that provides the same typed and voice-assisted shopping flow while browsing a supported store's site directly.
- Currently live across 25 real Pakistani clothing brands on Shopify.

## Tech Stack

- **Frontend:** React 19, Vite, TypeScript, Tailwind CSS v4
- **Backend:** Python 3.11+, FastAPI, SQLAlchemy (async) + Alembic, PostgreSQL (`asyncpg`), Redis, APScheduler
- **LLM/AI:** Google Gemini (`google-genai`), Groq (chat + Whisper transcription)
- **Browser extension:** TypeScript, Manifest V3, Vitest (unit tests), Playwright (E2E)
- **Auth/security:** JWT (`PyJWT`), `bcrypt`
- **Testing:** pytest, pytest-asyncio, pytest-cov
- **Deployment:** Vercel (frontend), Railway (FastAPI backend + Redis), Neon Postgres (database)

## Setup / Installation

### Prerequisites

- Node.js 18+
- Python 3.11+
- PostgreSQL 15+ locally, or a hosted service such as Neon
- Redis (a local Docker container is fine for development)
- API keys: [Gemini](https://aistudio.google.com/apikey), [Groq](https://console.groq.com/keys)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in DATABASE_URL, GEMINI_API_KEY, GROQ_API_KEY, REDIS_URL

alembic upgrade head    # creates schema + seeds the brand registry and collections
```

### Frontend

```bash
npm install
cp .env.local.example .env.local   # set VITE_API_BASE_URL=http://localhost:8000
```

### Chrome extension

```bash
cd extension
npm install
npm run build
```

### Local Redis (for development)

```bash
docker run -d --name dhaaga-redis -p 6379:6379 redis:7-alpine
```

## Usage

```bash
cd backend && uvicorn app.main:app --reload   # backend at http://localhost:8000 (GET /healthz to check DB + Redis)
npm run dev                                   # frontend at http://localhost:3000
```

For the extension: build it (`npm run build` in `extension/`), then load `extension/dist` as an unpacked extension from `chrome://extensions` with Developer mode enabled. The backend must be running for it to work.

### Testing

```bash
cd backend
pytest                              # full suite with coverage
pytest tests/unit/nlp/ -v           # a specific area
pytest --cov-report=html            # HTML coverage report
```

```bash
npx tsc --noEmit                    # frontend type-checking
cd extension && npm run typecheck && npm test && npm run test:e2e
```

## Current scope

**Deferred (not built):** delivery-time badges, cost-optimized "cheapest look" clustering, and brands whose storefronts aren't on Shopify.

**Known limitation:** brand coverage skews toward mass-market ready-to-wear and streetwear — searches for specialty categories a given brand simply doesn't carry (e.g. bridal lehengas) will come back thin or empty rather than showing mismatched results.
