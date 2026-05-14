-- Migration 004: Add shiprocket as a valid source type
-- Also adds shipping_cost and rto as valid metric names (enforced at app layer, not DB).

ALTER TABLE metric_events DROP CONSTRAINT IF EXISTS metric_events_source_check;

ALTER TABLE metric_events
    ADD CONSTRAINT metric_events_source_check
    CHECK (source IN ('shopify', 'meta_ads', 'gsheets', 'shiprocket'));
