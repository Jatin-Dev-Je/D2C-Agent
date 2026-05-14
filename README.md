# D2C AI Employee

AI employees for D2C brands — a cross-tool intelligence layer that connects your SaaS stack, normalizes your data, and answers business questions with grounded citations.

---

## 1. What You Built

A FastAPI backend that pulls data from Shopify, Meta Ads, and Google Sheets every 15 minutes, normalizes every row into a source-agnostic schema with full provenance, and serves a Claude-powered chat layer where every numerical claim is traceable back to the exact source row that produced it. An autonomous AdWatchdog agent runs every 6 hours, detects ad anomalies, and logs grounded recommendations with an estimated ₹ saving — without executing anything. The system is multi-tenant from day one: all data is isolated by `merchant_id` at the database layer via Supabase RLS.

**Stack:** FastAPI · Anthropic Claude (tool-use) · Supabase (PostgreSQL + RLS) · Upstash Redis (rate limiting) · APScheduler · structlog · Pydantic v2

---

## 2. Connectors — Which 3, Why These 3

| Connector | Source | Why |
|-----------|--------|-----|
| **Shopify** | Orders, refunds, AOV | Every D2C brand has Shopify. Revenue and order data is the foundation — without it you can't compute ROAS, profit, or refund rate. |
| **Meta Ads** | Campaign spend, impressions, clicks | Meta is the dominant paid channel for D2C brands in India. Ad spend without revenue context is noise; combined it gives ROAS, the single most-watched metric. |
| **Google Sheets** | COGS per SKU | COGS almost never lives in a SaaS tool. It lives in a spreadsheet. Including it lets the system answer "what's my actual margin?" — the question most D2C founders can't answer without an hour in Excel. |

These three together make the first meaningful cross-tool question answerable: **"What is my ROAS this month, and am I actually profitable after COGS?"** That's the question the product exists to answer.

---

## 3. Schema — Why This Shape

### One table, not three

All normalized metrics go into a single `metric_events` table regardless of source. A cross-source question like "what's my profit margin?" requires joining revenue (Shopify), COGS (Sheets), and ad spend (Meta). A flat table makes that a range scan. Separate tables make it a three-way join with schema negotiation on every query.

### Provenance on every row

```
source          TEXT    -- 'shopify' | 'meta_ads' | 'gsheets'
source_row_id   TEXT    -- 'shopify_order_12345', 'meta_campaign_abc_2024-01-01'
raw_payload     JSONB   -- exact upstream API response
synced_at       TIMESTAMPTZ
```

Every row carries the exact upstream identifier it came from. This is what makes citation grounding real: the AI doesn't just say "₹4.2L revenue" — it says "₹4.2L revenue [shopify_order_12345, shopify_order_12346, ...]". The evaluator can verify any number back to its source row.

The unique constraint `(merchant_id, source, source_row_id)` makes all ingestion idempotent — re-syncing the same order never creates duplicates.

### `dimensions` as JSONB

Flexibility vs type-safety tradeoff. Shopify rows carry `order_id`, `customer_email`, `financial_status`. Meta rows carry `campaign_id`, `campaign_name`. A typed discriminated union per source would be cleaner but requires a schema migration every time a connector adds a field. JSONB gets us to v0 and the tradeoff is documented in the Eval section.

---

## 4. Chat — Tool Schema and Citation Contract

### Tools exposed to Claude

| Tool | Purpose |
|------|---------|
| `query_metrics` | Raw row retrieval for a metric + date range (max 100 rows) |
| `get_metric_summary` | Aggregated total — "what was total revenue in April?" |
| `compare_metric_periods` | Period-over-period — "how did ROAS change week-over-week?" |
| `get_campaign_performance` | Campaign-level Meta Ads aggregation |
| `get_roas_summary` | Cross-source ROAS = revenue / ad_spend |

### How the citation contract works

1. Claude calls a tool. The tool returns rows with `source_row_id` on each one.
2. `LLMService` wraps every result in a `CitedValue` containing the metric value + the list of `source_row_ids` that produced it.
3. Before any response reaches the user, `enforce_grounded_response()` runs server-side: it extracts every numeric token from the answer text and rejects the response if no `cited_values` are present. Uncited numbers do not survive.
4. `CitationTrace` records the full aggregation lineage — which rows were summed, which operation was performed — so the answer is auditable end-to-end.

Confidence is computed from citation coverage: `high` if 5+ source rows and 2+ cited values, `medium` if 2+ rows, `low` otherwise.

### Streaming

The `/chat/stream` endpoint uses Anthropic's native token streaming API (`AsyncAnthropic.messages.stream()`). Tool-resolution calls are synchronous and sequential (deterministic). Once all tools are resolved, the final response streams token-by-token. Clients receive `processing` events during tool resolution and `token` events for each text chunk.

---

## 5. Agent — What It Does, Why This One

### AdWatchdog

Runs every 6 hours per merchant. Analyzes the last 7 days vs the previous 7 days and detects:

| Detection | Trigger | Action |
|-----------|---------|--------|
| Spend spike | Current spend > 1.5× previous | Log recommendation + estimated ₹ saving (excess vs baseline) |
| ROAS decline | Current ROAS < previous ROAS | Log recommendation with both period values cited |
| Low engagement | Campaign with >10k impressions and <50 clicks | Log recommendation citing the campaign |
| Zero spend | No Meta ad spend in current window | Alert — budget may have run out or campaign paused |

Every recommendation is backed by `source_row_ids`. The `estimated_saving_inr` field is populated with the actual excess spend (current − previous) for spend spikes. The agent **never executes anything** — it logs a `proposed_action` with `executed: false` and `status: "proposed"`.

### Why this agent

Ad spend is the most actionable metric in D2C. A 20% spend spike on a Meta campaign is almost always a budget misconfiguration or an algorithm that found a bad audience. Catching it in 6 hours vs the next morning's manual check saves real money. The ₹ saving estimate gives the founder a concrete number to act on rather than a vague alert. Agents that watch passive metrics (like revenue trends) are informational; agents that watch spend are operational.

---

## 6. Scale — 1 Merchant to 10,000

### What's already built for scale

| Layer | What exists |
|-------|-------------|
| **Multi-tenancy** | Supabase RLS — all queries enforce `merchant_id = auth.uid()`. Cross-merchant data leakage is impossible at the DB layer. |
| **Rate limiting** | Upstash Redis — 60 req/min per merchant on all API routes including chat. |
| **Idempotent ingestion** | Unique constraint on `(merchant_id, source, source_row_id)` — safe to re-sync without duplicates. |
| **Structured logging** | Every log line carries `merchant_id` and `request_id` — full traceability at any scale. |
| **Scheduler isolation** | Each merchant's sync jobs are isolated — one merchant's connector failure doesn't affect others. |

### What breaks first (honest)

**1. APScheduler (breaks at ~100 merchants)**
APScheduler runs in a single Python process. At 100 merchants × 3 connectors × every 15 minutes = 300 sync executions per cycle in one process. Thread pool saturation hits before CPU. Fix: Celery + Redis, or a managed job queue (Trigger.dev, Inngest).

**2. Connector credentials (breaks at merchant #2)**
Every connector reads a single global token from environment variables. 10,000 merchants need 10,000 different Shopify API keys, Meta access tokens, and Google service accounts. Fix: a `merchant_credentials` table with tokens encrypted at rest (e.g., Supabase Vault), passed per-fetch rather than at startup.

**3. `get_metric_rows` row limit (breaks at high data density)**
The repository caps at 500 rows per date-range query. A high-volume Shopify store with 500+ orders in a 30-day window will hit this. Fix: cursor pagination at the DB layer + streaming aggregation instead of loading all rows into memory.

**4. `get_distinct_merchant_ids` (breaks at scale)**
Currently scans `metric_events` to find distinct merchant IDs (capped at 10,000 rows). Fix: a dedicated `merchants` table updated on first sync.

**5. LLM cost at scale**
10,000 merchants × 1 chat query per day × tool-use round-trips ≈ non-trivial Anthropic spend. Fix: request-level caching for identical queries (same merchant + same question within a 15-min window), prompt caching for the system prompt.

---

## 7. Eval — Where It Breaks

| Issue | Severity | Notes |
|-------|----------|-------|
| JWT signature not verified | High | `validate_bearer_token` decodes base64 but never checks the signature against a Supabase JWT secret. Forged tokens will authenticate. Fix: verify against `SUPABASE_JWT_SECRET`. |
| Connector credentials are single-tenant | High | Only one Shopify/Meta/Sheets credential set per deployment. Multi-merchant credential store not built. |
| `dimensions` is untyped JSONB | Medium | Cross-source dimension joins (e.g., "which campaign drove the most refunded orders?") require knowing the shape at query time. No schema enforcement per source. |
| Streaming is sequential during tool calls | Low | Tool-resolution calls are non-streaming. `processing` events fire between tool calls but no tokens flow until the final response. |
| APScheduler is single-process | High at scale | Documented above. Fine for demo, breaks at ~100 merchants. |
| AdWatchdog thresholds are magic numbers | Low | 1.5× spend spike, 50 clicks — hardcoded, not configurable per merchant. |
| `metric_events.merchant_id` is stored as TEXT | Low | Migration uses UUID type. Application stores merchant_id from JWT `sub` claim which can be any string. Type mismatch will cause failures if `sub` is not a valid UUID. |
| No write tools in chat | Medium | The chat layer can only read. A D2C founder asking "pause the low-engagement campaign" gets an answer but no action. |
| Langfuse configured, not wired | Low | LLM observability keys are in config but no traces are emitted. |

---

## 8. Hours Spent

~22 hours across 4 sessions over 3 days.

- Day 1 (~8h): Schema design, connector implementations (Shopify + Meta + Sheets), base agent, LLM service tool-use loop
- Day 2 (~9h): Citation enforcement pipeline, grounding contract, scheduler, API routes, Supabase migrations
- Day 3 (~5h): Bug fixes (scheduler syntax, save_agent_log, lazy GSheets init), real streaming, rate limiting, README

---

## 9. What I'd Do With Another Week

1. **Per-merchant credential store** — `merchant_credentials` table with Supabase Vault encryption. OAuth flows for Shopify and Meta. This is the single most important architectural gap.
2. **Celery + Redis to replace APScheduler** — proper distributed job queue with retry visibility, dead letter queues, and horizontal scaling.
3. **Webhook receivers** — Shopify `orders/create` and `orders/updated` webhooks for real-time ingestion instead of 15-minute polling.
4. **A second agent: RefundSpikeAgent** — watches Shopify refund rates by SKU. High refund rate on a specific product is an ops signal (supplier quality, description mismatch). More actionable than a second ad watchdog.
5. **Confidence from data freshness** — factor last-synced timestamp into confidence score. If the last Shopify sync was 3 hours ago, "high" confidence is a lie.
6. **Chat write tools** — tool to pause a Meta campaign via Graph API (with a hard confirmation gate). This turns the AI from "advisor" to "employee".
7. **`merchants` table** — replaces the `metric_events` scan for merchant discovery. O(1) lookup, foundation for per-merchant settings and credential storage.
8. **Prompt caching** — the system prompt and tool schemas are static per request. Anthropic prompt caching would cut ~60% of token cost on every chat call.

---

## Setup

### Prerequisites
- Python 3.11+
- A Supabase project
- An Anthropic API key

### Install

```bash
pip install -r backend/requirements.txt
```

### Database

Run migrations in order against your Supabase project:

```sql
-- Run in Supabase SQL editor:
-- 1. backend/schema/migrations/001_initial.sql
-- 2. backend/schema/migrations/002_rls_policies.sql
```

### Environment

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

Required:
```
ANTHROPIC_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
```

Optional (connectors degrade gracefully if not set):
```
SHOPIFY_SHOP_DOMAIN=...
SHOPIFY_ACCESS_TOKEN=...
META_ACCESS_TOKEN=...
META_AD_ACCOUNT_ID=...
GOOGLE_SHEET_ID=...
GOOGLE_SERVICE_ACCOUNT_JSON=...
```

### Run

```bash
uvicorn backend.main:app --reload --port 8000
```

API docs at `http://localhost:8000/docs`

### Test

```bash
pytest backend/tests/ -v
```

---

## API Reference

| Method | Route | Description |
|--------|-------|-------------|
| `POST` | `/chat/query` | Grounded chat (sync) |
| `POST` | `/chat/stream` | Grounded chat (token streaming SSE) |
| `GET` | `/agents/logs` | List agent run logs |
| `POST` | `/agents/trigger` | Manually trigger AdWatchdog |
| `GET` | `/metrics/summary` | Aggregated metric total |
| `GET` | `/metrics/compare` | Period-over-period comparison |
| `GET` | `/metrics/roas` | ROAS summary |
| `GET` | `/metrics/campaigns` | Campaign performance |
| `GET` | `/connectors/health` | Connector health status |
| `POST` | `/connectors/sync` | Trigger manual sync (background) |
| `GET` | `/dashboard` | 30-day overview |
| `GET` | `/health` | System health check |

All routes except `/health`, `/docs`, `/redoc` require `Authorization: Bearer <token>`.

---

## A Note on AI Tools

Claude Code (claude-sonnet-4-6) was used extensively throughout implementation — typed method signatures, boilerplate, and filling in implementation details from design specs. All architecture decisions were made by the developer: the choice of these three connectors, the single-table schema with provenance, the citation grounding contract, the dispatch-table LLM service design, and the judgment calls in this README. Claude wrote code; the developer decided what to build and why.
