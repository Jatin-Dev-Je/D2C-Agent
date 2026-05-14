from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agents.base_agent import AgentExecutionResult
from backend.schema.models import AgentRunLog, CitedValue, SourceType


# ── AgentExecutionResult ──────────────────────────────────────────────────────

def test_agent_execution_result_defaults() -> None:
    result = AgentExecutionResult(
        success=True,
        observations=["Spend spiked"],
        recommendations=["Pause campaign X"],
    )
    assert result.success is True
    assert result.cited_values == []
    assert result.estimated_saving_inr is None
    assert result.metadata == {}


def test_agent_run_log_executed_always_false() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError) as exc_info:
        AgentRunLog(
            agent_name="watchdog",
            merchant_id="550e8400-e29b-41d4-a716-446655440000",
            observation="Spend spike detected",
            reasoning="20% above baseline",
            proposed_action="Reduce daily budget",
            executed=True,
        )
    assert "executed" in str(exc_info.value)


def test_agent_run_log_status_field() -> None:
    log = AgentRunLog(
        agent_name="watchdog",
        merchant_id="550e8400-e29b-41d4-a716-446655440000",
        observation="All metrics stable",
        reasoning="No anomalies found",
        proposed_action="No action required",
        status="success",
    )
    assert log.executed is False
    assert log.status == "success"


# ── AdWatchdogAgent agent ──────────────────────────────────────────────────────────

class TestAdWatchdogAgent:
    def _make_watchdog(self) -> object:
        from backend.agents.ad_watchdog import AdWatchdogAgent
        with patch("backend.agents.ad_watchdog.MetricsService") as mock_svc_cls:
            with patch("backend.agents.ad_watchdog.MetricsRepository"):
                watchdog = AdWatchdogAgent.__new__(AdWatchdogAgent)
                watchdog.metrics_service = mock_svc_cls.return_value
                watchdog.logger = MagicMock()
                return watchdog

    @pytest.mark.asyncio
    async def test_returns_result_with_recommendations(self) -> None:
        from backend.agents.ad_watchdog import AdWatchdogAgent

        watchdog = self._make_watchdog()
        watchdog.metrics_service.get_roas_summary = AsyncMock(return_value={
            "revenue": Decimal("10000"),
            "ad_spend": Decimal("2000"),
            "roas": Decimal("5.0"),
        })
        watchdog.metrics_service.get_campaign_performance_summary = AsyncMock(return_value={
            "campaigns": [],
            "total_spend": Decimal("2000"),
            "total_impressions": Decimal("50000"),
            "total_clicks": Decimal("1000"),
        })
        watchdog.metrics_service.repository = MagicMock()
        watchdog.metrics_service.repository.get_metric_rows = AsyncMock(return_value=[])

        result = await watchdog._safe_execute(merchant_id="test-merchant")
        assert isinstance(result, AgentExecutionResult)
        assert len(result.recommendations) >= 1

    @pytest.mark.asyncio
    async def test_handles_no_data_gracefully(self) -> None:
        from backend.agents.ad_watchdog import AdWatchdogAgent
        from backend.chat.citation import CitationValidationError

        watchdog = self._make_watchdog()
        watchdog.metrics_service.get_roas_summary = AsyncMock(
            side_effect=CitationValidationError("No data")
        )
        watchdog.metrics_service.get_campaign_performance_summary = AsyncMock(
            side_effect=CitationValidationError("No data")
        )
        watchdog.metrics_service.repository = MagicMock()
        watchdog.metrics_service.repository.get_metric_rows = AsyncMock(return_value=[])

        result = await watchdog._safe_execute(merchant_id="test-merchant")
        assert isinstance(result, AgentExecutionResult)
        assert len(result.recommendations) >= 1
