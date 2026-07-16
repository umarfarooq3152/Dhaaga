# Dhaaga session handoff — 2026-07-16

## Goal

Make Dhaaga understand natural shopping intent with an LLM—typos, Roman Urdu,
cultural events, audience, age, colour, product, vibe and conversational
refinements—without maintaining a spelling-by-spelling production dictionary.
Results must never mix gender/age or pad the grid with unrelated products.

## Completed

### LLM-first intent

- Added a shared typed intent contract used by Gemini and Groq.
- Added operations: `new_search`, `refine`, `replace`, `remove_filter`,
  `show_more`, and `conversation_only`.
- Added standalone `semantic_query`, hard constraints, soft preferences and
  per-field confidence.
- Product, occasion, colour and style semantics now come from the LLM.
  Deterministic code is limited to session controls and validation of strict
  facts such as audience, exact child age, size and numeric budget.
- Intent cache keys include the full session context and contract version, so
  phrases such as “blue instead” cannot leak between conversations.
- Provider formatting errors in hard/soft constraint labels are normalized
  without losing the valid intent.
- Generic words such as “clothing” are not treated as product categories.
- Visual moods such as “bright” and “vibrant” are style preferences, not fake
  literal colours.

### Strict result safety

- Gender is a hard gate; unknown audience is not accepted for a gendered query.
- Adult/child and exact child age are hard gates and are revalidated immediately
  before pagination.
- Product category, explicit colour, size and budget remain strict unless the
  LLM explicitly marks a subjective preference as soft.
- Exact matches are ordered first; a sparse set is filled with near-matches by
  relaxing one soft signal at a time. Occasions are always eligible for this
  relevance fallback because merchant event metadata is incomplete.
- Broad taxonomy requests such as western wear do not create an inferred
  garment category; shirts, tops, tees, dresses, jeans, skirts and trousers can
  all compete by evidence.
- Non-apparel catalog entries and fully out-of-stock products are excluded.
- Event merchandise such as henna stencils cannot qualify as event clothing.
- A conflicting named celebration is excluded, while broad store labels such as
  “casual” do not incorrectly contradict a suitable nikah/mehndi garment.
- Zero-result and broadened-result replies say what was unavailable and what was
  changed; cards are never silently presented as exact matches.

### Semantic catalog and hybrid retrieval

- Added `ProductSemantics` with a versioned profile:
  - canonical product family
  - audiences
  - occasions
  - verified attributes
  - internal retrieval text
- New/cron-refreshed products are enriched during ingestion.
- Existing Redis products are upgraded lazily after strict filtering; no cache
  clear or full re-scrape is required.
- Internal semantic retrieval text is excluded from API responses.
- Ranking now combines trusted lexical evidence, cultural-event suitability and
  semantic-profile relevance.
- Semantic scoring only reorders already-valid candidates and cannot bypass
  audience, age, category, colour, size, budget or availability gates.
- Cheap strict category/style evidence now runs before expensive event scoring.
  Live warm latency for the test query improved from about 21.3s to 3.5s; a
  cold worker request was about 8.4s.
- Large ranking work runs outside the asyncio event loop; `/docs`, wishlist and
  other requests remain responsive during a search.

### UX and resilience already completed

- Web and extension show a minimum response transition instead of instant
  hardcoded-looking replies.
- Gemini HTTP 429/quota failures now open an in-process provider circuit for a
  configurable cooldown (default 300 seconds), so subsequent uncached intent
  requests go directly to Groq instead of repeatedly paying for a known failure.
- Replaced the shut-down `gemini-2.0-flash` default with stable
  `gemini-3.1-flash-lite`, which Google positions for low-latency,
  high-volume structured extraction and lists on the standard free tier.
- Gemini is retried after the cooldown; timeouts and non-rate-limit failures do
  not open the circuit and therefore retain the previous retry behavior.
- Greetings are friendly and do not trigger random products or gender loops.
- Previous products remain visible during recoverable timeouts/errors.
- Session reset and client-state rehydration no longer randomly return users to
  onboarding.
- Frontend runs at `http://localhost:3000`; backend runs on port `8000`.

### Evaluation assets

- `docs/SEARCH_PERSONA_CORPUS.md` contains 100 realistic personas/scenarios.
- CI verifies that all numbered scenarios 1–100 exist and have observable
  expected outcomes.
- Unit tests cover semantic enrichment, semantic reranking, audience isolation,
  child age, category/color correctness, relaxation behavior and session state.
- Rebased the Generation department correction onto `0005_add_users` as the
  single `0006_generation_department` Alembic head; `alembic upgrade head` now
  succeeds on the configured Neon database.
- Presentation verification passed: 488 backend tests, frontend production
  build/type-check, extension production build/type-check, 14 extension unit
  tests, and all 4 Chromium extension E2E tests.

## Live verification

Query:

> something bright and embroidered for my cousins mehnndi, women

Resolved state:

- occasion: `mehndi`
- department: `women`
- styles: `bright`, `embroidered`
- hard: `occasion`, `department`
- soft: `style_descriptors`
- semantic query: `bright and embroidered clothing for women's mehndi`
- result: 6 women’s bright embroidered suits; no gender mixing

Latency on the current local environment:

- cold worker/catalog decode: approximately 8.4 seconds
- warm repeat: approximately 3.5 seconds
- unrelated API route remained responsive in approximately 0.02–0.04 seconds
  while search was running

## Provider status

The replacement Gemini key and `gemini-3.1-flash-lite` primary path were
verified live on 2026-07-16 with a valid structured shopping-intent response and
no HTTP 429. Set `GEMINI_RATE_LIMIT_COOLDOWN_SECONDS` to tune the default
five-minute cooldown used if the free-tier limit is reached later.

## Recommended next steps

1. Add timing telemetry around intent, Redis decode, filtering, event scoring,
   semantic ranking and response serialization; display p50/p95 in logs.
2. Convert the highest-risk rows in the 100-persona corpus into executable
   snapshot/catalog evaluations, then record intent accuracy, hard-constraint
   violations, Precision@10, zero-result rate and latency.
3. Add a persisted database/search index if the catalog grows beyond the
   current in-memory/Redis scale. Store semantic profiles and availability in
   Postgres; use pgvector only after an offline relevance comparison proves it
   improves the ontology-based hybrid scorer.
4. Hide the small public `semantics` metadata object from product responses too
   if API payload minimization becomes important; the large retrieval text is
   already hidden.

## Verification commands

```bash
cd /home/umar/Documents/Dhaaga/backend
.venv/bin/pytest -q --no-cov

cd /home/umar/Documents/Dhaaga
npm run lint
```

Start backend:

```bash
cd /home/umar/Documents/Dhaaga/backend
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The repository has many intentional uncommitted changes from this work. Do not
reset or discard them; inspect `git status --short` and continue incrementally.
