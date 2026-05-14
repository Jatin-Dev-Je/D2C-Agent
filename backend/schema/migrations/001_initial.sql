CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS metric_events (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    merchant_id   UUID NOT NULL,
    source        TEXT NOT NULL CHECK (source IN ('shopify', 'meta_ads', 'gsheets')),
    source_row_id TEXT NOT NULL,
    metric_name   TEXT NOT NULL,
    value         NUMERIC NOT NULL,
    currency      TEXT NOT NULL DEFAULT 'INR',
    dimensions    JSONB NOT NULL DEFAULT '{}',
    occurred_at   TIMESTAMPTZ NOT NULL,
    synced_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    raw_payload   JSONB
);

CREATE INDEX IF NOT EXISTS idx_metric_events_merchant_id
    ON metric_events (merchant_id);

CREATE INDEX IF NOT EXISTS idx_metric_events_metric_name
    ON metric_events (metric_name);

CREATE INDEX IF NOT EXISTS idx_metric_events_occurred_at
    ON metric_events (occurred_at DESC);

CREATE INDEX IF NOT EXISTS idx_metric_events_merchant_source
    ON metric_events (merchant_id, source);

CREATE UNIQUE INDEX IF NOT EXISTS idx_metric_events_dedup
    ON metric_events (merchant_id, source, source_row_id);

CREATE TABLE IF NOT EXISTS agent_run_logs (
    id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_name        TEXT NOT NULL,
    merchant_id       UUID NOT NULL,
    triggered_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    observation       TEXT NOT NULL,
    reasoning         TEXT NOT NULL,
    proposed_action   TEXT NOT NULL,
    estimated_saving  NUMERIC,
    citations         TEXT[] NOT NULL DEFAULT '{}',
    executed          BOOLEAN NOT NULL DEFAULT FALSE,
    status            TEXT NOT NULL DEFAULT 'proposed'
);

CREATE INDEX IF NOT EXISTS idx_agent_run_logs_merchant_id
    ON agent_run_logs (merchant_id);

CREATE INDEX IF NOT EXISTS idx_agent_run_logs_triggered_at
    ON agent_run_logs (triggered_at DESC);

ALTER TABLE metric_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_run_logs ENABLE ROW LEVEL SECURITY;