CREATE POLICY IF NOT EXISTS metric_events_merchant_isolation
    ON metric_events
    FOR ALL
    TO authenticated
    USING (merchant_id = auth.uid()::text)
    WITH CHECK (merchant_id = auth.uid()::text);

CREATE POLICY IF NOT EXISTS agent_run_logs_merchant_isolation
    ON agent_run_logs
    FOR ALL
    TO authenticated
    USING (merchant_id = auth.uid()::text)
    WITH CHECK (merchant_id = auth.uid()::text);

GRANT ALL ON metric_events TO service_role;
GRANT ALL ON agent_run_logs TO service_role;
