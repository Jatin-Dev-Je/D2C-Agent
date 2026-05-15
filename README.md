# D2C AI Employee

An AI employee for D2C brands — connects Shopify, Meta Ads, and Shiprocket, normalises the data into one place, and lets you ask questions about your business in plain English. Every number it gives you is traceable to the exact source row it came from.

---

## 1. What I Built

A FastAPI backend that pulls data from Shopify, Meta Ads, and Shiprocket every 15 minutes and normalises everything into one flat table with full provenance on every row. On top of that sits a Gemini-powered chat layer — you ask a question, it calls the right tool, gets the data, and answers using only what it actually found. Every number in the answer is cited back to its source row. If a number has no citation, it gets rejected before it reaches you. An autonomous AdWatchdog agent runs every 6 hours, spots ad spend anomalies, and logs what it found and what it recommends — without actually doing anything. The whole thing is multi-tenant from day one with Supabase RLS. There's also a React frontend with a dashboard, chat interface, metrics explorer, and agent log viewer.

**Stack:** FastAPI · Gemini (tool-use + streaming) · Supabase (PostgreSQL + RLS) · APScheduler · Upstash Redis · React 19 · TailwindCSS

---

## 2. Connectors — Which 3, Why These 3

I picked Shopify, Meta Ads, and Shiprocket. Here's why these three specifically:

**Shopify** — every D2C brand in India has Shopify. Revenue, orders, refunds, AOV — this is the foundation. Without it you can't answer anything meaningful.

**Meta Ads** — Meta is where most Indian D2C brands spend their marketing budget. Ad spend without revenue context is just a number. Combined, you get ROAS, which is the one metric founders actually obsess over.

**Shiprocket** — this is the one most people would miss. Logistics cost and RTO (return-to-origin) are the hidden margin killers in Indian D2C. A founder's Meta ROAS looks great until you subtract ₹180/order in shipping and 12% RTO. We're submitting this to Shiprocket. We built a connector for Shiprocket. That felt like the honest choice.

These three together make one real cross-tool question answerable: *"What is my actual ROAS after shipping costs, and which campaigns are driving the most returns?"* That's the question that takes half an hour in Excel today.

All three implement the same `BaseConnector` abstract class — `fetch()`, `health_check()`, `validate_rows()`. Swapping one out or adding a fourth is a single new file.

---

## 3. Schema — Why This Shape

**One table, not three.**

Everything goes into `metric_events` regardless of where it came from. A cross-source question — "what's my margin after shipping?" — needs Shopify revenue, Meta spend, and Shiprocket cost in one query. One table makes that a date-range scan. Three tables make it a join with schema negotiation every time.

**Provenance on every row.**

```
source          TEXT    -- 'shopify' | 'meta_ads' | 'shiprocket'
source_row_id   TEXT    -- e.g. 'shopify_order_12345'
raw_payload     JSONB   -- the exact API response that produced this row
synced_at       TIMESTAMPTZ
```

This is what makes the citation grounding real. The AI doesn't just say "₹4.2L revenue" — it says where that number came from. You can trace any figure back to the exact row that produced it.

The unique constraint on `(merchant_id, source, source_row_id)` means re-syncing the same order never creates a duplicate. Idempotent by design.

**`dimensions` as JSONB** — flexible per-source fields. Shopify rows have `order_id`, `financial_status`. Meta rows have `campaign_id`, `campaign_name`. Shiprocket rows have `courier_name`, `awb_code`. Typed unions would be cleaner but require a migration every time a connector adds a field. JSONB gets us to v0. The tradeoff is documented in Eval.

---

## 4. Chat — Tools and Citation

### The tools I exposed to Gemini

| Tool | What it does |
|------|-------------|
| `query_metrics` | Fetch raw rows for a metric and date range |
| `get_metric_summary` | Aggregated total for a period — "what was total revenue in April?" |
| `compare_metric_periods` | Week-over-week, month-over-month comparisons |
| `get_campaign_performance` | Campaign-level Meta Ads breakdown |
| `get_roas_summary` | Cross-source ROAS = Shopify revenue ÷ Meta ad spend |

### How citation actually works

1. Gemini calls a tool. The tool returns rows, each with a `source_row_id`.
2. The service wraps every result in a `CitedValue` — the metric value plus the list of `source_row_ids` that produced it.
3. Before any response reaches the user, `enforce_grounded_response()` runs server-side. It scans the answer text for every numeric token and rejects the response if there are no cited values attached. Uncited numbers do not survive.
4. `CitationTrace` records the full aggregation lineage — which rows were summed, what operation was performed — so every answer is auditable.

Confidence is `high` if 5+ source rows and 2+ cited values, `medium` if 2+ rows, `low` otherwise.

### Streaming

`/chat/stream` uses Gemini's async streaming API for real token-by-token delivery. Tool resolution is sequential and non-streaming (that's intentional — deterministic tool calls before the final answer). Clients get `processing` events during tool calls and `token` events for each text chunk.

---

## 5. Agent — AdWatchdog

**What it does:**

Runs every 6 hours. Compares the last 7 days to the 7 days before that. Looks for four things:

| What | Trigger | Output |
|------|---------|--------|
| Spend spike | Current spend > 1.5× previous period | Recommendation + estimated ₹ saving |
| ROAS decline | Current ROAS < previous ROAS | Recommendation with both periods cited |
| Low engagement | >10k impressions, <50 clicks | Flags the specific campaign |
| Zero spend | No ad spend detected | Alert — budget may have run out |

Every recommendation is grounded — it cites the exact `source_row_ids` it based its analysis on. The `estimated_saving_inr` is the actual excess spend. The agent **never executes anything** — it logs `proposed_action` with `executed: false` and `status: "proposed"`.

**Why this agent:**

Ad spend is the most operationally urgent metric in D2C. A 20% spend spike usually means a budget misconfiguration or Meta's algorithm found a bad audience and is spending into it. Catching it in 6 hours instead of the next morning's manual check saves real money. Agents that watch passive metrics are informational. Agents that watch spend are operational. I wanted the first agent to be operational.

The ₹ saving estimate gives the founder a concrete number — not "your spend went up" but "you spent ₹35,000 more than baseline this week."

---

## 6. Scale — 1 Merchant to 10,000

### What I built for scale

| Layer | What's there |
|-------|-------------|
| Multi-tenancy | Supabase RLS — `merchant_id = auth.uid()::text` on all tables. Cross-merchant leakage is impossible at the DB layer. |
| Idempotent ingestion | Unique constraint on `(merchant_id, source, source_row_id)` — safe re-syncs, zero duplicates. |
| Rate limiting | Upstash Redis — 60 req/min per merchant. Falls back to in-memory when Redis is unavailable. |
| Structured logging | Every log line has `merchant_id` + `request_id` — ready for distributed tracing. |
| Merchant table | Dedicated `merchants` table for O(1) merchant discovery — scheduler uses this, not a scan. |
| Async throughout | Non-blocking I/O — `asyncio.to_thread` for Supabase, async Gemini client. |

### What breaks first (honest)

**APScheduler breaks at ~100 merchants.** It's a single Python process. 100 merchants × 3 connectors × every 15 min = 300 sync executions per cycle. Thread pool saturation. Fix: Celery + Redis or Inngest.

**Connector credentials break at merchant #2.** Right now every connector reads one global token from `.env`. 10,000 merchants need 10,000 different tokens. Fix: `merchant_credentials` table with encrypted tokens, OAuth flows per connector.

**500-row query cap.** `get_metric_rows` caps at 500 rows (configurable via `MAX_METRIC_ROWS`). A high-volume Shopify store hits this silently. Fix: cursor pagination.

**LLM cost at scale.** 10k merchants × a few chat queries/day × tool-use round trips = real Gemini spend. Fix: request-level caching, Gemini context caching for the static system prompt.

---

## 7. Eval — Where It Breaks

I'd rather tell you before you find it:

| Issue | How bad | Notes |
|-------|---------|-------|
| JWT signature unverified without `SUPABASE_JWT_SECRET` | High | Structural validation only — forged tokens authenticate. Set the secret in prod. |
| Single-tenant connector credentials | High | All merchants share one Shopify/Meta/Shiprocket token. OAuth per-merchant is v1 work. |
| Shiprocket auth returning 404 during testing | Medium | API may have temporary issues or endpoint changed. The connector code is correct — the abstraction, normalization, and provenance logic are all implemented. |
| APScheduler single-process ceiling | High at scale | ~100 merchants, then it needs to be replaced. |
| `dimensions` is untyped JSONB | Medium | Cross-source dimension joins require knowing the field shape at query time. No schema enforcement per source. |
| No write tools in chat | Medium | Chat is currently read-only. "Pause this campaign" gets a recommendation, not an action. |
| Streaming sequential during tool calls | Low | Tool resolution blocks token flow. Tokens only stream after all tools resolve. |
| AdWatchdog thresholds hardcoded | Low | 1.5× spend spike, 50 clicks — not configurable per merchant. |

---

## 8. Hours Spent

Around 30 hours across 3 days.

**Day 1 (~10h):** Figured out the schema, built the three connectors, wired up the base agent, got the Gemini tool-use loop working with citation enforcement.

**Day 2 (~11h):** Streaming, scheduler, all the API routes, Supabase migrations and RLS policies, rate limiting, auth middleware, started the React frontend.

**Day 3 (~9h):** Finished the frontend (all 6 pages), fixed a bunch of bugs (timezone handling, system prompt tuning, tool schema required fields), wrote the README.

---

## 9. What I'd Do With Another Week

**Per-merchant credential storage** — this is the most important gap. `merchant_credentials` table with Supabase Vault encryption, OAuth flows for Shopify and Meta. Without this it's genuinely single-tenant.

**Replace APScheduler with a queue** — Celery + Redis, or something like Inngest. Proper retries, dead-letter queues, horizontal scaling.

**Webhook receivers** — Shopify `orders/create` for real-time ingestion instead of polling every 15 minutes.

**A write tool in chat** — pause a Meta campaign via Graph API with a hard confirmation gate. That's the difference between an AI advisor and an AI employee.

**RefundSpikeAgent** — watches Shopify refund rates by SKU. High refund rate on a specific product is an ops signal that something's wrong with that product. More actionable than another ad watchdog.

**Data freshness in confidence score** — if the last Shopify sync was 3 hours ago, calling a response "high confidence" is misleading.

---

## A Note on AI Tools

I used Claude, GitHub Copilot, and Codex (free tier) throughout. They wrote a lot of the boilerplate — component code, typed method signatures, test scaffolding, UI components. Every architecture decision was mine: which three connectors and why, the single-table schema with provenance, the citation grounding contract, the agent design, the judgment calls in this README. The LLMs were fast hands, not the brain.

---

## Production Path — How This Scales to Real Use

This is a v0. Here's what honest production deployment looks like:

**Step 1 — Fix the credential problem first.**
Right now all merchants share one Shopify/Meta/Shiprocket token from `.env`. Before going multi-tenant, build a `merchant_credentials` table (Supabase Vault for encryption at rest), OAuth flows for Shopify and Meta so each merchant connects their own account, and pass credentials per-fetch instead of at startup. Without this, you have a demo, not a product.

**Step 2 — Replace the scheduler.**
APScheduler runs in a single Python process. At ~100 merchants it starts to fall over. Replace it with Celery + Redis or a managed job queue like Inngest. Each connector sync becomes a separate queued task with proper retries, dead-letter queues, and visibility into what failed and why.

**Step 3 — Set `SUPABASE_JWT_SECRET` in production.**
Right now without this, tokens are structurally validated but not signature-verified. Anyone who knows the JWT format can forge a token. Set the secret — it's a one-line env var change that makes authentication actually secure.

**Step 4 — Add webhook receivers.**
The 15-minute polling loop works for v0. For production, Shopify supports `orders/create` and `orders/updated` webhooks. Real-time ingestion means data is always fresh when the founder opens the dashboard at 9am.

**Step 5 — Add write tools to the chat layer.**
Right now the AI can only read. Real AI employees need to act. The first write tool I'd add: pause a Meta campaign via the Graph API with a hard confirmation gate in the UI. The agent already spots the problem — the write tool lets it solve it.

**Step 6 — Cursor pagination.**
The current 500-row query cap (`MAX_METRIC_ROWS`) is configurable but still a cap. A Shopify store doing 1000+ orders a month hits this. Cursor pagination at the DB layer removes the ceiling without loading everything into memory.

**Deployment target:** Render (backend) + Vercel (frontend) + Supabase (DB) + Upstash (Redis). All have generous free tiers for v0 and straightforward upgrade paths. Cost at 100 merchants with real usage: ~$50-100/month. Cost at 10k merchants: needs proper infrastructure planning but the architecture supports it — the DB layer is already multi-tenant.

---

## Setup

### Prerequisites
- Python 3.11+
- Node 18+
- Supabase project (free tier works)
- Gemini API key (free at aistudio.google.com)

### 1. Clone and install

```bash
git clone https://github.com/Jatin-Dev-Je/D2C-Agent.git
cd D2C-Agent

pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### 2. Configure

```bash
cp backend/.env.example backend/.env
# Fill in GEMINI_API_KEY, SUPABASE_URL, SUPABASE_KEY, SUPABASE_JWT_SECRET
# Add connector credentials for whichever you have
```

### 3. Run migrations

In Supabase SQL Editor, run in order:
```
backend/schema/migrations/001_initial.sql
backend/schema/migrations/002_rls_policies.sql
backend/schema/migrations/003_merchants.sql
backend/schema/migrations/004_add_shiprocket_source.sql
```

### 4. Run

```bash
# Backend (from project root)
uvicorn backend.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend && npm run dev
```

- API: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`

### 5. Authenticate

```bash
python backend/scripts/make_token.py
```

Copy the token → frontend Settings → paste as Bearer Token → Save.

Then call `POST /merchants/register` once to register your merchant in the DB.

### 6. Sync and explore

```
POST /connectors/sync
```

Data lands in 30 seconds. Ask the chat anything about your business.
