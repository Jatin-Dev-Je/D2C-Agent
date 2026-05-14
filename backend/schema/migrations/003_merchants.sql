-- Migration 003: Merchants table
-- Replaces the 10k-row metric_events scan for merchant discovery.

CREATE TABLE IF NOT EXISTS merchants (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id  TEXT        NOT NULL UNIQUE,
    email        TEXT        NOT NULL UNIQUE,
    role         TEXT        NOT NULL DEFAULT 'merchant',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS merchants_merchant_id_idx ON merchants (merchant_id);
CREATE INDEX IF NOT EXISTS merchants_email_idx       ON merchants (email);

ALTER TABLE merchants ENABLE ROW LEVEL SECURITY;

-- Service role has full access (used by backend)
CREATE POLICY merchants_service_role ON merchants
    FOR ALL TO service_role
    USING (true)
    WITH CHECK (true);

-- Auto-update updated_at on row change
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS merchants_updated_at ON merchants;
CREATE TRIGGER merchants_updated_at
    BEFORE UPDATE ON merchants
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
