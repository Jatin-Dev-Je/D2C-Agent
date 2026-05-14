from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from backend.agents.base_agent import AgentExecutionResult, BaseAgent
from backend.core.logging import get_logger
from backend.repositories.metrics_repository import MetricsRepository
from backend.schema.models import CitedValue, MetricName, Provenance, SourceType
from backend.services.metrics_service import MetricsService


logger = get_logger(__name__)


@dataclass(slots=True)
class WatchdogWindow:
    """UTC analysis window for current and previous period comparisons."""

    start: datetime
    end: datetime


class AdWatchdogAgent(BaseAgent):
    """Deterministic ad performance watchdog that emits grounded recommendations only."""

    def __init__(self, metrics_service: MetricsService | None = None) -> None:
        """Initialize the watchdog with a metrics service dependency."""

        self.metrics_service = metrics_service or MetricsService(repository=MetricsRepository())

    @property
    def agent_name(self) -> str:
        """Return the stable agent name used for observability and audit logs."""

        return "ad_watchdog"

    def _current_window(self) -> WatchdogWindow:
        """Return the current seven-day UTC window ending now."""

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=7)
        return WatchdogWindow(start=start, end=end)

    def _previous_window(self) -> WatchdogWindow:
        """Return the previous seven-day UTC window immediately before the current window."""

        current = self._current_window()
        return WatchdogWindow(
            start=current.start - timedelta(days=7),
            end=current.start,
        )

    def _normalize_decimal(self, value: Any) -> Decimal:
        """Convert numeric values into Decimal safely for deterministic comparisons."""

        return Decimal(str(value or 0))

    def _normalize_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize row payloads into stable comparison-friendly dictionaries."""

        normalized_rows: list[dict[str, Any]] = []
        for row in rows:
            source = SourceType(str(row.get("source", SourceType.META_ADS.value)))
            source_row_id = str(row.get("source_row_id", "")).strip()
            if not source_row_id:
                continue

            normalized_rows.append(
                {
                    "id": str(row.get("id", source_row_id)),
                    "merchant_id": str(row.get("merchant_id", "")).strip(),
                    "metric_name": MetricName(str(row.get("metric_name", MetricName.AD_SPEND.value))),
                    "value": self._normalize_decimal(row.get("value", 0)),
                    "currency": str(row.get("currency", "INR")),
                    "dimensions": dict(row.get("dimensions") or {}),
                    "occurred_at": row.get("occurred_at"),
                    "provenance": Provenance(
                        source=source,
                        source_row_id=source_row_id,
                        source_url=row.get("source_url"),
                        synced_at=datetime.fromisoformat(
                            str(row.get("synced_at", datetime.now(timezone.utc).isoformat())).replace("Z", "+00:00")
                        ),
                        raw_payload=row.get("raw_payload"),
                    ),
                }
            )

        return normalized_rows

    def _build_cited_value(
        self,
        *,
        metric_name: MetricName,
        value: Decimal,
        rows: list[dict[str, Any]],
        source: SourceType = SourceType.META_ADS,
        currency: str = "INR",
    ) -> CitedValue:
        """Build a citation-safe summary value from normalized rows."""

        source_row_ids = sorted(
            {
                str(row["provenance"].source_row_id)
                for row in rows
                if row.get("provenance") and str(row["provenance"].source_row_id).strip()
            }
        )

        if not source_row_ids:
            raise ValueError("recommendations without provenance are invalid")

        return CitedValue(
            value=value,
            currency=currency,
            metric_name=metric_name.value,
            source_row_ids=source_row_ids,
            source=source,
        )

    def _build_observation(self, message: str) -> str:
        """Format a concise deterministic observation string."""

        return message.strip()

    def _build_recommendation(self, message: str) -> str:
        """Format a deterministic recommendation string."""

        return message.strip()

    def _build_metadata(
        self,
        *,
        current_window: WatchdogWindow,
        previous_window: WatchdogWindow,
        findings: list[str],
    ) -> dict[str, Any]:
        """Build replay-safe metadata for audit and eval pipelines."""

        return {
            "analysis_type": "deterministic_ad_watchdog",
            "current_window_start": current_window.start.isoformat(),
            "current_window_end": current_window.end.isoformat(),
            "previous_window_start": previous_window.start.isoformat(),
            "previous_window_end": previous_window.end.isoformat(),
            "finding_count": len(findings),
            "findings": findings,
        }

    async def _analyze_spend_spike(
        self,
        *,
        merchant_id: str,
        current_window: WatchdogWindow,
        previous_window: WatchdogWindow,
    ) -> tuple[str | None, CitedValue | None, Decimal | None]:
        """Detect a significant ad spend spike against the previous period.

        Returns (recommendation, cited_value, excess_spend_inr).
        excess_spend_inr is the INR saving if spend were reverted to previous level.
        """

        raw_current_rows = await self.metrics_service.repository.get_metric_rows(
            merchant_id=merchant_id,
            metric_name=MetricName.AD_SPEND,
            start_date=current_window.start,
            end_date=current_window.end,
        )
        previous_spend = await self.metrics_service.get_metric_summary(
            merchant_id=merchant_id,
            metric_name=MetricName.AD_SPEND,
            start_date=previous_window.start,
            end_date=previous_window.end,
        )

        current_value = sum(
            (self._normalize_decimal(r.get("value", 0)) for r in raw_current_rows),
            Decimal("0"),
        )
        previous_value = self._normalize_decimal(previous_spend["total"])

        if previous_value == 0:
            return None, None, None

        if current_value <= previous_value * Decimal("1.5"):
            return None, None, None

        rows = await self.metrics_service.build_citation_context(
            merchant_id=merchant_id,
            source_row_ids=sorted(
                {str(r.get("source_row_id", "")).strip() for r in raw_current_rows if str(r.get("source_row_id", "")).strip()}
            ),
        )
        normalized_rows = self._normalize_rows(rows)
        cited_value = self._build_cited_value(
            metric_name=MetricName.AD_SPEND,
            value=current_value,
            rows=normalized_rows,
        )
        excess = current_value - previous_value
        return (
            self._build_recommendation(
                "Ad spend increased significantly compared to the previous period."
            ),
            cited_value,
            excess if excess > 0 else None,
        )

    async def _analyze_roas_decline(
        self,
        *,
        merchant_id: str,
        current_window: WatchdogWindow,
        previous_window: WatchdogWindow,
    ) -> tuple[str | None, CitedValue | None]:
        """Detect declining ROAS against the previous period."""

        current_roas = await self.metrics_service.get_roas_summary(
            merchant_id=merchant_id,
            start_date=current_window.start,
            end_date=current_window.end,
        )
        previous_roas = await self.metrics_service.get_roas_summary(
            merchant_id=merchant_id,
            start_date=previous_window.start,
            end_date=previous_window.end,
        )

        current_value = self._normalize_decimal(current_roas["roas"])
        previous_value = self._normalize_decimal(previous_roas["roas"])

        if current_value >= previous_value:
            return None, None

        revenue_rows = await self.metrics_service.repository.get_metric_rows(
            merchant_id=merchant_id,
            metric_name=MetricName.REVENUE,
            start_date=current_window.start,
            end_date=current_window.end,
        )
        ad_spend_rows = await self.metrics_service.repository.get_metric_rows(
            merchant_id=merchant_id,
            metric_name=MetricName.AD_SPEND,
            start_date=current_window.start,
            end_date=current_window.end,
        )
        rows = await self.metrics_service.build_citation_context(
            merchant_id=merchant_id,
            source_row_ids=sorted(
                {
                    str(row.get("source_row_id", "")).strip()
                    for row in revenue_rows + ad_spend_rows
                    if str(row.get("source_row_id", "")).strip()
                }
            ),
        )
        normalized_rows = self._normalize_rows(rows)
        cited_value = self._build_cited_value(
            metric_name=MetricName.ROAS,
            value=current_value,
            rows=normalized_rows,
        )
        return (
            self._build_recommendation(
                "ROAS declined compared to the previous period."
            ),
            cited_value,
        )

    async def _analyze_engagement(
        self,
        *,
        merchant_id: str,
        current_window: WatchdogWindow,
    ) -> tuple[str | None, CitedValue | None]:
        """Detect campaigns with high impressions but low clicks."""

        campaign_summary = await self.metrics_service.get_campaign_performance_summary(
            merchant_id=merchant_id,
            start_date=current_window.start,
            end_date=current_window.end,
        )

        campaigns = campaign_summary.get("campaigns", [])
        if not campaigns:
            return None, None

        highest_impressions = max(
            campaigns,
            key=lambda item: self._normalize_decimal(item["impressions"]),
        )
        impressions = self._normalize_decimal(highest_impressions["impressions"])
        clicks = self._normalize_decimal(highest_impressions["clicks"])

        if impressions <= Decimal("10000") or clicks >= Decimal("50"):
            return None, None

        rows = await self.metrics_service.build_citation_context(
            merchant_id=merchant_id,
            source_row_ids=list(highest_impressions.get("source_row_ids", [])),
        )
        normalized_rows = self._normalize_rows(rows)
        cited_value = self._build_cited_value(
            metric_name=MetricName.IMPRESSIONS,
            value=impressions,
            rows=normalized_rows,
        )
        return (
            self._build_recommendation(
                "Campaign generating impressions but low engagement."
            ),
            cited_value,
        )

    async def _analyze_zero_spend(
        self,
        *,
        merchant_id: str,
        current_window: WatchdogWindow,
    ) -> tuple[str | None, CitedValue | None]:
        """Detect current-period zero ad spend."""

        current_spend = await self.metrics_service.get_metric_summary(
            merchant_id=merchant_id,
            metric_name=MetricName.AD_SPEND,
            start_date=current_window.start,
            end_date=current_window.end,
        )

        current_value = self._normalize_decimal(current_spend["total"])
        if current_value != 0:
            return None, None

        raw_rows = await self.metrics_service.repository.get_metric_rows(
            merchant_id=merchant_id,
            metric_name=MetricName.AD_SPEND,
            start_date=current_window.start,
            end_date=current_window.end,
        )
        source_row_ids = sorted(
            {str(r.get("source_row_id", "")).strip() for r in raw_rows if str(r.get("source_row_id", "")).strip()}
        )

        # No rows means the connector hasn't synced yet — can't cite absence of data.
        if not source_row_ids:
            return None, None

        rows = await self.metrics_service.build_citation_context(
            merchant_id=merchant_id,
            source_row_ids=source_row_ids,
        )
        normalized_rows = self._normalize_rows(rows)
        if not normalized_rows:
            return None, None

        cited_value = self._build_cited_value(
            metric_name=MetricName.AD_SPEND,
            value=current_value,
            rows=normalized_rows,
        )
        return (
            self._build_recommendation("No ad spend detected in current period."),
            cited_value,
        )

    async def run(self, merchant_id: str) -> AgentExecutionResult:
        """Analyze ad performance deterministically and return grounded recommendations."""

        normalized_merchant_id = merchant_id.strip()
        if not normalized_merchant_id:
            raise ValueError("merchant_id cannot be empty")

        log = logger.bind(
            merchant_id=normalized_merchant_id,
            agent_name=self.agent_name,
        )

        current_window = self._current_window()
        previous_window = self._previous_window()

        observations: list[str] = []
        recommendations: list[str] = []
        cited_values: list[CitedValue] = []
        findings: list[str] = []
        estimated_saving_inr: Decimal | None = None

        spend_recommendation, spend_citation, spend_excess = await self._analyze_spend_spike(
            merchant_id=normalized_merchant_id,
            current_window=current_window,
            previous_window=previous_window,
        )
        if spend_recommendation and spend_citation:
            observations.append(self._build_observation("Ad spend spike detected."))
            recommendations.append(spend_recommendation)
            cited_values.append(spend_citation)
            findings.append("spend_spike")
            if spend_excess is not None:
                estimated_saving_inr = spend_excess

        roas_recommendation, roas_citation = await self._analyze_roas_decline(
            merchant_id=normalized_merchant_id,
            current_window=current_window,
            previous_window=previous_window,
        )
        if roas_recommendation and roas_citation:
            observations.append(self._build_observation("ROAS decline detected."))
            recommendations.append(roas_recommendation)
            cited_values.append(roas_citation)
            findings.append("roas_decline")

        engagement_recommendation, engagement_citation = await self._analyze_engagement(
            merchant_id=normalized_merchant_id,
            current_window=current_window,
        )
        if engagement_recommendation and engagement_citation:
            observations.append(self._build_observation("Low engagement campaign detected."))
            recommendations.append(engagement_recommendation)
            cited_values.append(engagement_citation)
            findings.append("low_engagement")

        zero_spend_recommendation, zero_spend_citation = await self._analyze_zero_spend(
            merchant_id=normalized_merchant_id,
            current_window=current_window,
        )
        if zero_spend_recommendation and zero_spend_citation:
            observations.append(self._build_observation("Zero spend detected."))
            recommendations.append(zero_spend_recommendation)
            cited_values.append(zero_spend_citation)
            findings.append("zero_spend")

        if not recommendations:
            campaign_summary = await self.metrics_service.get_campaign_performance_summary(
                merchant_id=normalized_merchant_id,
                start_date=current_window.start,
                end_date=current_window.end,
            )
            campaigns = campaign_summary.get("campaigns", [])
            summary_rows = await self.metrics_service.build_citation_context(
                merchant_id=normalized_merchant_id,
                source_row_ids=[
                    source_row_id
                    for campaign in campaigns
                    for source_row_id in campaign.get("source_row_ids", [])
                ],
            )

            if summary_rows:
                normalized_rows = self._normalize_rows(summary_rows)
                cited_value = self._build_cited_value(
                    metric_name=MetricName.AD_SPEND,
                    value=self._normalize_decimal(campaign_summary.get("total_spend", 0)),
                    rows=normalized_rows,
                )
                cited_values.append(cited_value)

            observations.append(self._build_observation("No material ad anomalies detected."))
            recommendations.append(
                self._build_recommendation(
                    "Ad performance is stable in the current analysis window."
                )
            )
            findings.append("stable")

        metadata = self._build_metadata(
            current_window=current_window,
            previous_window=previous_window,
            findings=findings,
        )

        log.info(
            "ad_watchdog_analysis_complete",
            finding_count=len(findings),
            recommendations=len(recommendations),
            cited_values=len(cited_values),
        )

        return AgentExecutionResult(
            success=True,
            observations=observations,
            recommendations=recommendations,
            cited_values=cited_values,
            metadata=metadata,
            estimated_saving_inr=estimated_saving_inr,
        )