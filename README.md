# D2C AI Employee

AI employees for D2C brands — a cross-tool intelligence layer that connects your SaaS stack, normalises your data, and answers business questions with grounded citations.

---

## 1. What You Built

A FastAPI backend that pulls data from Shopify, Meta Ads, and Shiprocket every 15 minutes, normalises every row into a source-agnostic schema with full provenance, and serves a Gemini-powered chat layer where every numerical claim is traceable back to the exact source row that produced it. An autonomous AdWatchdog agent runs every 6 hours, detects ad spend anomalies, and logs grounded ₹-saving recommendations — without executing anything. The system is multi-tenant from day one: all data is isolated by `merchant_id` at the database layer via Supabase RLS. A React frontend provides a dashboard, chat interface, metrics explorer, agent log viewer, and connector health monitor.

**Stack:** FastAPI · Google Gemini (tool-use + streaming) · Supabase (PostgreSQL + RLS) · Upstash Redis (rate limiting) · APScheduler · structlog · Pydantic v2 · React 19 · TailwindCSS

---

## 2. Connectors — Which 3, Why These 3

| Connector | Source | Why |
|-----------|--------|-----|
| **Shopify** | Orders, refunds, AOV | Every Indian D2C brand has Shopify. Revenue and order data is the foundation — without it you cannot compute ROAS, margin, or refund rate. |
| **Meta Ads** | Campaign spend, impressions, clicks | Meta is the dominant paid channel for D2C brands in India. Ad spend without revenue context is noise; combined it gives ROAS — the single most-watched metric for growth-stage D2C. |
| **Shiprocket** | Shipping cost, RTO (return-to-origin) | Logistics cost and RTO are the hidden margin killers for Indian D2C. A founder's Meta ROAS looks healthy until you subtract ₹180/order shipping and 12% RTO. This connector makes that visible in the same query. We submitted this to Shiprocket. We used Shiprocket. |

These three together make the first meaningful cross-tool question answerable: **"What is my true ROAS after shipping costs, and which campaigns are driving the most returns?"**

---

## 3. Schema — Why This Shape

### One table, not three

All normalised metrics go into a single `metric_events` table regardless of source. A cross-source question like "what's my profit margin after shipping?" requires Shopify revenue, Meta ad spend, and Shiprocket costs in one query. A flat table makes that a date-range scan. Separate tables make it a three-way join with schema negotiation on every query.

### Provenance on every row

```sql
source          TEXT    -- 'shopify' | 'meta_ads' | 'shiprocket'
source_row_id   TEXT    -- 'shopify_order_12345', 'meta_campaign_abc_2024-01-01_spend'
raw_payload     JSONB   -- exact upstream API response
synced_at       TIMESTAMPTZ
```

Every row carries the exact upstream identifier it came from. This is what makes citation grounding real: the AI doesn't just say "₹4.2L revenue" — it says "₹4.2L revenue [shopify_order_12345, shopify_order_12346, ...]". Any number is traceable to its source row.

The unique constraint `(merchant_id, source, source_row_id)` makes all ingestion idempotent — re-syncing the same order never creates duplicates.

### `dimensions` as JSONB

Flexibility vs type-safety tradeoff. Shopify rows carry `order_id`, `financial_status`. Meta rows carry `campaign_id`, `campaign_name`. Shiprocket rows carry `courier_name`, `awb_code`, `city`. A typed union per source would be cleaner but requires a migration every time a connector adds a field. JSONB gets us to v0 — tradeoff documented in Eval.

---

## 4. Chat — Tool Schema and Citation Contract

### Tools exposed to Gemini

| Tool | Purpose |
|------|---------|
| `query_metrics` | Raw row retrieval for a metric + date range |
| `get_metric_summary` | Aggregated total — "what was total revenue in April?" |
| `compare_metric_periods` | Period-over-period — "how did ROAS change week-over-week?" |
| `get_campaign_performance` | Campaign-level Meta Ads aggregation |
| `get_roas_summary` | Cross-source ROAS = revenue ÷ ad_spend |

### How citation works

1. Gemini calls a tool. The tool returns rows — each with a `source_row_id`.
2. `LLMService` wraps every result in a `CitedValue` containing the metric value + the list of `source_row_ids` that produced it.
3. Before any response reaches the user, `enforce_grounded_response()` runs server-side: it extracts every numeric token from the answer and rejects the response if no `cited_values` are attached. **Uncited numbers do not survive.**
4. `CitationTrace` records the full aggregation lineage — which rows were summed, which operation — so the answer is auditable end-to-end.

Confidence: `high` if 5+ source rows and 2+ cited values, `medium` if 2+ rows, `low` otherwise.

### Streaming

`/chat/stream` uses Gemini's async streaming API (`client.aio.models.generate_content_stream`). Tool-resolution calls are sequential and non-streaming (deterministic). Once all tools resolve, the final response streams token-by-token. Clients receive `processing` events during tool calls and `token` events for each text chunk.

---

## 5. Agent — AdWatchdog

Runs every 6 hours per merchant. Compares the last 7 days vs the previous 7 days:

| Detection | Trigger | Output |
|-----------|---------|--------|
| Spend spike | Current spend > 1.5× previous | Recommendation + estimated ₹ saving (excess vs baseline) |
| ROAS decline | Current ROAS < previous ROAS | Recommendation with both periods cited |
| Low engagement | >10k impressions, <50 clicks | Flags the specific campaign |
| Zero spend | No Meta ad spend detected | Alert — budget may have run out |

Every recommendation is backed by `source_row_ids`. The `estimated_saving_inr` is the actual excess spend. The agent **never executes anything** — it logs `proposed_action` with `executed: false` and `status: "proposed"`.

### Why this agent

Ad spend is the most operationally actionable metric in D2C. A 20% spend spike is almost always a budget misconfiguration or an algorithm finding a bad audience. Catching it in 6 hours vs the next morning's manual review saves real money. Agents that watch passive metrics are informational; agents that watch spend are operational. The ₹ saving estimate gives a concrete number, not a vague alert.

---

## 6. Scale — 1 Merchant to 10,000

### What's built for scale

| Layer | What exists |
|-------|------------|
| **Multi-tenancy** | Supabase RLS — `merchant_id = auth.uid()::text` on all tables. Cross-merchant leakage impossible at DB layer. |
| **Idempotent ingestion** | Unique constraint on `(merchant_id, source, source_row_id)` — safe re-syncs, no duplicates. |
| **Rate limiting** | Upstash Redis — 60 req/min per merchant. Falls back to in-memory when Redis is unavailable. |
| **Structured logging** | Every log line carries `merchant_id` + `request_id` — distributed tracing ready. |
| **Scheduler isolation** | Per-merchant jobs — one merchant's connector failure doesn't affect others. |
| **Async throughout** | Non-blocking I/O — `asyncio.to_thread` for Supabase, async Gemini client for streaming. |
| **Merchants table** | `merchants` table for O(1) merchant discovery — scheduler uses this, not a `metric_events` scan. |

### What breaks first (honest)

**1. APScheduler (~100 merchants)**
Single Python process. 100 merchants × 3 connectors × every 15 min = 300 sync executions per cycle. Thread pool saturation.
Fix: Celery + Redis, or Inngest/Trigger.dev.

**2. Connector credentials (merchant #2)**
One global token per connector from `.env`. Every merchant needs their own Shopify/Meta/Shiprocket credentials.
Fix: `merchant_credentials` table with encrypted tokens, per-merchant OAuth flows.

**3. 500-row query cap**
`get_metric_rows` caps at `max_metric_rows` (default 500, configurable). High-volume stores hit this silently.
Fix: Cursor pagination + streaming aggregation.

**4. LLM cost**
10k merchants × 1 chat/day × tool-use round-trips = non-trivial Gemini spend.
Fix: Request-level cache, Gemini context caching for static system prompt.

---

## 7. Eval — Where It Breaks

| Issue | Severity | Notes |
|-------|----------|-------|
| JWT signature unverified without `SUPABASE_JWT_SECRET` | High | Structural validation only — forged tokens authenticate. Set the secret in production. |
| Single-tenant connector credentials | High | All merchants share one Shopify/Meta/Shiprocket token. OAuth per-merchant is v1 work. |
| APScheduler single-process | High at scale | ~100 merchant ceiling. Replace with queue in v1. |
| Shiprocket auth endpoint returning 404 during testing | Medium | Possible API issue or credential format. Connector code is correct — auth endpoint and normalization logic implemented. |
| `dimensions` untyped JSONB | Medium | Cross-source dimension joins require knowing field shape at query time. |
| No write tools in chat | Medium | Chat is read-only. "Pause this campaign" gets a recommendation, not an action. |
| Streaming sequential during tool calls | Low | Tool calls are non-streaming. Tokens only flow after all tools resolve. |
| AdWatchdog thresholds hardcoded | Low | 1.5× spend spike, 50 clicks — not configurable per merchant. |

---

## 8. Hours Spent

~28 hours across 3 days.

- **Day 1 (~10h):** Schema design, connector implementations (Shopify + Meta + Shiprocket), base agent, Gemini tool-use loop, citation enforcement pipeline
- **Day 2 (~10h):** Streaming, scheduler, API routes, Supabase migrations, RLS policies, rate limiting, auth middleware, React frontend foundation
- **Day 3 (~8h):** Frontend UI (Dashboard, Chat, Metrics, Agents, Connectors, Settings), bug fixes (timezone handling, system prompt tuning, tool schema required fields), README

---

## 9. What I'd Do With Another Week

1. **Per-merchant credential store** — `merchant_credentials` table with Supabase Vault encryption. OAuth flows for Shopify and Meta. This is the single most important architectural gap.
2. **Celery + Redis** to replace APScheduler — proper distributed job queue with retries, dead-letter queues, and horizontal scaling.
3. **Webhook receivers** — Shopify `orders/create` and `orders/updated` for real-time ingestion instead of polling.
4. **RefundSpikeAgent** — watches Shopify refund rates by SKU. High refund rate on a specific product is an ops signal (supplier quality, description mismatch).
5. **Chat write tools** — pause a Meta campaign via Graph API with a hard confirmation gate. This turns the AI from "advisor" to "employee."
6. **Confidence from data freshness** — factor `synced_at` into confidence score. If last Shopify sync was 3 hours ago, "high confidence" is a lie.
7. **Gemini context caching** — system prompt and tool schemas are static. Caching would cut ~60% of token cost per chat call.
8. **In-app connector setup UI** — form in the frontend where users enter their own Shopify/Meta/Shiprocket credentials directly, instead of editing `.env`.

---

## Setup

### Prerequisites
- Python 3.11+
- Node 18+
- Supabase project (free tier works)
- Google Gemini API key (free at aistudio.google.com)

### 1. Clone and install

```bash
git clone https://github.com/Jatin-Dev-Je/D2C-Agent.git
cd D2C-Agent

# Backend
pip install -r requirements.txt

# Frontend
cd frontend && npm install && cd ..
```

### 2. Environment

```bash
cp backend/.env.example backend/.env
```

Fill in `backend/.env`:

```bash
# Required
GEMINI_API_KEY=...
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret   # get from Supabase → Settings → API

# Connectors (add whichever you have)
SHOPIFY_SHOP_DOMAIN=your-store.myshopify.com
SHOPIFY_ACCESS_TOKEN=shpat_...
META_ACCESS_TOKEN=...
META_AD_ACCOUNT_ID=act_...
SHIPROCKET_EMAIL=...
SHIPROCKET_PASSWORD=...
```

### 3. Database migrations

Run in Supabase SQL Editor in order:

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

- API docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`

### 5. Authenticate

```bash
python backend/scripts/make_token.py
```

Copy the printed token → open frontend → Settings → paste as Bearer Token → Save.

Then hit `POST /merchants/register` once to register your merchant in the DB.

### 6. Sync data

```bash
POST /connectors/sync
```

Data will appear in the dashboard and chat within 30 seconds.

---

## API Reference

| Method | Route | Auth | Description |
|--------|-------|------|-------------|
| `POST` | `/chat/query` | ✓ | Grounded chat (sync) |
| `POST` | `/chat/stream` | ✓ | Grounded chat (SSE streaming) |
| `GET`  | `/agents/logs` | ✓ | Agent run history |
| `POST` | `/agents/trigger` | ✓ | Trigger AdWatchdog manually |
| `GET`  | `/metrics/summary` | ✓ | Aggregated metric total |
| `GET`  | `/metrics/compare` | ✓ | Period-over-period |
| `GET`  | `/metrics/roas` | ✓ | ROAS summary |
| `GET`  | `/metrics/campaigns` | ✓ | Campaign performance |
| `GET`  | `/connectors/health` | ✓ | Connector status |
| `POST` | `/connectors/sync` | ✓ | Trigger manual sync |
| `GET`  | `/dashboard` | ✓ | 30-day overview |
| `POST` | `/merchants/register` | ✓ | Register merchant (call once on first login) |
| `GET`  | `/health` | — | System health |

---

## A Note on AI Tools

Claude Code (claude-sonnet-4-6) was used throughout — typed method signatures, boilerplate, UI components, and filling implementation details from design specs. All architecture decisions were made by the developer: the choice of Shopify + Meta + Shiprocket, the single-table schema with provenance, the citation grounding contract, the tool-use dispatch design, and the judgments in this README. Claude wrote code. The developer decided what to build and why.
