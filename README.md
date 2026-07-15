# Dhaaga

A conversational shopping assistant for Pakistani fashion. Describe what you're
looking for in plain language — "an elegant Eid outfit under Rs. 30,000" — and
Dhaaga searches live across multiple real Pakistani clothing brands, refines
results turn by turn, and links out to the brand's own store to complete the
purchase.

Dhaaga is an aggregator, not a marketplace: it never handles checkout. Every
product links back to the brand that sells it.

## How it works

- **Live-fetch, no product database.** Products are pulled on demand from each
  brand's public Shopify storefront (`/products.json`) and held in a short-lived
  Redis cache (~20–30 min) refreshed by a background job. There's no persistent
  product catalog to keep in sync — the brand's own site is the source of truth.
- **Conversational search.** A message goes through a fast-path rule classifier
  first (for common refinements like "cheaper" or "show more"), falling back to
  an LLM (Gemini, with Groq as an automatic fallback) for full intent extraction
  only when needed. Extracted intent is a *diff* merged into session state —
  style preferences accumulate turn over turn, budget/color overwrite, and a
  topic change resets the deadline but keeps size/budget.
- **Brand-diversified, tiered ranking.** Structured filters (occasion, budget,
  size, color) narrow the pool; free-text style words are keyword-scored
  against title/description. Results are ranked by relevance tier first, then
  diversified by brand *within* each tier — so one brand's product-naming
  convention never crowds out everyone else, and irrelevant filler never
  outranks (or gets mixed into) genuine matches.
- **Data-quality filtering at ingestion.** Real Pakistani fashion brands sell
  more than clothes through the same Shopify store — home textiles, perfume,
  jewelry, fabric sold by the meter. Anything that isn't a wearable garment,
  is implausibly priced, or has no product image is excluded when a brand's
  catalog is fetched, not left for the search layer to filter around.

## Project structure

```
Dhaaga/
├── src/                  # Vite + React frontend
│   ├── api/              # Backend API client
│   ├── components/       # Screens: Onboarding, Discovery, Chat Search, Product Detail, Wishlist
│   └── hooks/            # useDeviceId, useWishlist, useSessionChat
├── backend/
│   ├── app/
│   │   ├── shopify/      # Live Shopify fetch + normalization + data-quality filtering
│   │   ├── services/     # product_cache_service, search_service, session_service
│   │   ├── llm/          # Gemini (primary) / Groq (fallback) intent extraction
│   │   ├── nlp/          # fast_path_classifier, diff_merge (session state merge rules)
│   │   ├── routers/      # /session, /products, /brands, /collections, /wishlist, /devices
│   │   └── db/, repositories/, schemas/
│   ├── migrations/       # Alembic
│   └── seed/             # Brand registry + curated collection seed data
└── docs/                 # PRD, TDD, feature spec, design tokens
```

## Setup

### Prerequisites

- Node.js 18+
- Python 3.11+
- A [Neon](https://neon.tech) Postgres project
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
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`. Check `GET /healthz` — it verifies both
the database and Redis connections.

### Frontend

```bash
npm install
cp .env.local.example .env.local   # set VITE_API_BASE_URL=http://localhost:8000
npm run dev
```

Frontend runs at `http://localhost:3000`.

### Chrome extension MVP

The MV3 extension is isolated under `extension/`. It searches only the active
Outfitters tab for the MVP, has no content script, and never manipulates the
store page. Groq credentials remain in the FastAPI backend; do not add an API
key to extension source, storage, or build output.

Start the backend, then build the unpacked extension:

```bash
cd extension
npm install
npm run typecheck
npm test
npm run build
```

Open `chrome://extensions`, enable Developer mode, choose **Load unpacked**,
and select `extension/dist`. The development manifest connects to
`http://localhost:8000`; update both `src/config.ts` and `manifest.json` when
pointing at a deployed HTTPS backend.

Voice requests are capped at 30 seconds in the popup and 5 MB at the backend.
Audio is sent to the backend and Groq for transcription, then discarded by
Dhaaga. Typed queries, transcripts, and product results are held only in
`chrome.storage.session` for short-lived popup recovery; there is no search
history. Product images are loaded from merchant CDNs with no referrer.

### Local Redis (for development)

```bash
docker run -d --name dhaaga-redis -p 6379:6379 redis:7-alpine
```

## Testing

```bash
cd backend
pytest                              # full suite with coverage
pytest tests/unit/nlp/ -v           # a specific area
pytest --cov-report=html            # HTML coverage report
```

Frontend type-checking:

```bash
npx tsc --noEmit
```

## Current scope

**Live:** 25 real Pakistani clothing brands (Shopify-based storefronts),
conversational search with multi-turn refinement, occasion/budget/color/size
filtering, curated editorial collections, a wishlist, and a Menswear/Womenswear
department preference set at onboarding that biases which brands show up.

**Deferred (not built):** voice search (mic button is currently a visual
toggle only, no real transcription), delivery-time badges, cost-optimized
"cheapest look" clustering, and brands whose storefronts aren't on Shopify
(they'd need HTML scraping or a headless browser instead of a JSON feed).

**Known limitation:** brand coverage skews toward mass-market ready-to-wear
and streetwear — searches for specialty categories a given brand simply
doesn't carry (e.g. bridal lehengas, which tend to be sold by dedicated
bridal boutiques rather than lawn/ready-to-wear retailers) will come back
thin or empty rather than showing mismatched results.

## Deployment

- **Frontend:** Vercel (static Vite build)
- **Backend:** Railway (FastAPI + Redis add-on, `alembic upgrade head` as a
  release-command hook, scheduled job refreshes the product cache)
- **Database:** Neon Postgres
