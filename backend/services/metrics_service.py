from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

import structlog

from backend.repositories.metrics_repository import MetricsRepository
from backend.schema.models import MetricName


DECIMAL_PRECISION = Decimal("0.01")

logger = structlog.get_logger(__name__)


def _normalize_datetime(value: datetime, field_name: str) -> datetime:
    """Validate timezone awareness and normalize datetimes to UTC."""

    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")

    return value.astimezone(timezone.utc)


def _normalize_decimal(value: Decimal | str | int | float) -> Decimal:
    """Normalize metric outputs to stable monetary precision."""

    decimal_value = Decimal(str(value))
    return decimal_value.quantize(DECIMAL_PRECISION, rounding=ROUND_HALF_UP)


def _safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    """Safely divide two Decimal values without raising on zero denominators."""

    if denominator == 0:
        return Decimal("0")

    return numerator / denominator


def _classify_trend(delta: Decimal, previous_value: Decimal) -> str:
    """Classify period movement into a stable trend label."""

    if previous_value == 0 and delta == 0:
        return "stable"

    if delta > 0:
        return "growing"

    if delta < 0:
        return "declining"

    return "stable"


def _ensure_string_list(values: list[str]) -> list[str]:
    """Strip blank identifiers while preserving order."""

    return [value.strip() for value in values if value and value.strip()]


@dataclass(slots=True)
class MetricsService:
    """
    Business intelligence orchestration layer for metrics analytics.

    This service centralizes calculations that should be shared by routers,
    AI tools, autonomous agents, and dashboard APIs.
    """

    repository: MetricsRepository

    async def get_metric_summary(
        self,
        merchant_id: str,
        metric_name: MetricName,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Return a metric summary for a merchant and date range."""

        normalized_start = _normalize_datetime(start_date, "start_date")
        normalized_end = _normalize_datetime(end_date, "end_date")

        rows = await self.repository.get_metric_rows(
            merchant_id=merchant_id,
            metric_name=metric_name,
            start_date=normalized_start,
            end_date=normalized_end,
        )

        total = sum(
            (_normalize_decimal(row.get("value", 0)) for row in rows),
            Decimal("0"),
        )

        log = logger.bind(merchant_id=merchant_id, metric_name=metric_name.value)
        log.info(
            "metric_summary_built",
            start_date=normalized_start.isoformat(),
            end_date=normalized_end.isoformat(),
            row_count=len(rows),
            total=str(total),
        )

        return {
            "metric_name": metric_name.value,
            "total": _normalize_decimal(total),
            "row_count": len(rows),
            "start_date": normalized_start,
            "end_date": normalized_end,
        }

    async def calculate_roas(
        self,
        revenue: Decimal,
        ad_spend: Decimal,
    ) -> Decimal:
        """Safely calculate ROAS using Decimal precision."""

        normalized_revenue = _normalize_decimal(revenue)
        normalized_ad_spend = _normalize_decimal(ad_spend)
        roas = _safe_divide(normalized_revenue, normalized_ad_spend)
        return _normalize_decimal(roas)

    async def get_roas_summary(
        self,
        merchant_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Build a grounded ROAS summary from repository-backed metrics."""

        normalized_start = _normalize_datetime(start_date, "start_date")
        normalized_end = _normalize_datetime(end_date, "end_date")

        revenue = await self.repository.get_metric_sum(
            merchant_id=merchant_id,
            metric_name=MetricName.REVENUE,
            start_date=normalized_start,
            end_date=normalized_end,
        )
        ad_spend = await self.repository.get_metric_sum(
            merchant_id=merchant_id,
            metric_name=MetricName.AD_SPEND,
            start_date=normalized_start,
            end_date=normalized_end,
        )
        roas = await self.calculate_roas(revenue=revenue, ad_spend=ad_spend)

        log = logger.bind(merchant_id=merchant_id)
        log.info(
            "roas_summary_built",
            start_date=normalized_start.isoformat(),
            end_date=normalized_end.isoformat(),
            revenue=str(revenue),
            ad_spend=str(ad_spend),
            roas=str(roas),
        )

        return {
            "merchant_id": merchant_id,
            "start_date": normalized_start,
            "end_date": normalized_end,
            "revenue": _normalize_decimal(revenue),
            "ad_spend": _normalize_decimal(ad_spend),
            "roas": roas,
        }

    async def compare_metric_periods(
        self,
        merchant_id: str,
        metric_name: MetricName,
        current_start: datetime,
        current_end: datetime,
        previous_start: datetime,
        previous_end: datetime,
    ) -> dict[str, Any]:
        """Compare metric performance across two periods and classify trend."""

        normalized_current_start = _normalize_datetime(current_start, "current_start")
        normalized_current_end = _normalize_datetime(current_end, "current_end")
        normalized_previous_start = _normalize_datetime(previous_start, "previous_start")
        normalized_previous_end = _normalize_datetime(previous_end, "previous_end")

        comparison = await self.repository.compare_metric_periods(
            merchant_id=merchant_id,
            metric_name=metric_name,
            current_start=normalized_current_start,
            current_end=normalized_current_end,
            previous_start=normalized_previous_start,
            previous_end=normalized_previous_end,
        )

        current_value = _normalize_decimal(comparison["current_value"])
        previous_value = _normalize_decimal(comparison["previous_value"])
        delta = _normalize_decimal(comparison["delta"])
        delta_percentage = _normalize_decimal(comparison["delta_percentage"])
        trend = _classify_trend(delta=delta, previous_value=previous_value)

        log = logger.bind(merchant_id=merchant_id, metric_name=metric_name.value)
        log.info(
            "metric_period_comparison_built",
            current_value=str(current_value),
            previous_value=str(previous_value),
            delta=str(delta),
            delta_percentage=str(delta_percentage),
            trend=trend,
        )

        return {
            "metric_name": metric_name.value,
            "current_value": current_value,
            "previous_value": previous_value,
            "delta": delta,
            "delta_percentage": delta_percentage,
            "trend": trend,
            "current_start": normalized_current_start,
            "current_end": normalized_current_end,
            "previous_start": normalized_previous_start,
            "previous_end": normalized_previous_end,
        }

    async def get_campaign_performance_summary(
        self,
        merchant_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Aggregate campaign analytics into an AI-friendly summary."""

        normalized_start = _normalize_datetime(start_date, "start_date")
        normalized_end = _normalize_datetime(end_date, "end_date")

        campaign_rows = await self.repository.get_campaign_performance(
            merchant_id=merchant_id,
            start_date=normalized_start,
            end_date=normalized_end,
        )

        if not campaign_rows:
            log = logger.bind(merchant_id=merchant_id)
            log.info(
                "campaign_performance_summary_empty",
                start_date=normalized_start.isoformat(),
                end_date=normalized_end.isoformat(),
            )
            return {
                "merchant_id": merchant_id,
                "start_date": normalized_start,
                "end_date": normalized_end,
                "campaign_count": 0,
                "top_spender": None,
                "top_clicks": None,
                "highest_impressions": None,
                "campaigns": [],
            }

        normalized_rows: list[dict[str, Any]] = []
        for row in campaign_rows:
            normalized_rows.append(
                {
                    "merchant_id": row.get("merchant_id", merchant_id),
                    "campaign_id": str(row.get("campaign_id", "unknown")),
                    "campaign_name": str(row.get("campaign_name", "unknown")),
                    "spend": _normalize_decimal(row.get("spend", 0)),
                    "impressions": _normalize_decimal(row.get("impressions", 0)),
                    "clicks": _normalize_decimal(row.get("clicks", 0)),
                    "source_row_ids": _ensure_string_list(
                        list(row.get("source_row_ids", []))
                    ),
                }
            )

        top_spender = max(normalized_rows, key=lambda item: item["spend"])
        top_clicks = max(normalized_rows, key=lambda item: item["clicks"])
        highest_impressions = max(normalized_rows, key=lambda item: item["impressions"])

        total_spend = sum((row["spend"] for row in normalized_rows), Decimal("0"))
        total_clicks = sum((row["clicks"] for row in normalized_rows), Decimal("0"))
        total_impressions = sum(
            (row["impressions"] for row in normalized_rows),
            Decimal("0"),
        )

        log = logger.bind(merchant_id=merchant_id)
        log.info(
            "campaign_performance_summary_built",
            start_date=normalized_start.isoformat(),
            end_date=normalized_end.isoformat(),
            campaign_count=len(normalized_rows),
            total_spend=str(total_spend),
            total_clicks=str(total_clicks),
            total_impressions=str(total_impressions),
        )

        return {
            "merchant_id": merchant_id,
            "start_date": normalized_start,
            "end_date": normalized_end,
            "campaign_count": len(normalized_rows),
            "total_spend": _normalize_decimal(total_spend),
            "total_clicks": _normalize_decimal(total_clicks),
            "total_impressions": _normalize_decimal(total_impressions),
            "top_spender": top_spender,
            "top_clicks": top_clicks,
            "highest_impressions": highest_impressions,
            "campaigns": normalized_rows,
        }

    async def build_citation_context(
        self,
        merchant_id: str,
        source_row_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Fetch exact cited rows and shape them for grounded AI use."""

        cleaned_source_row_ids = _ensure_string_list(source_row_ids)
        log = logger.bind(merchant_id=merchant_id)

        if not cleaned_source_row_ids:
            log.info(
                "citation_context_skipped",
                reason="empty_source_row_ids",
            )
            return []

        rows = await self.repository.get_rows_by_source_ids(
            merchant_id=merchant_id,
            source_row_ids=cleaned_source_row_ids,
        )

        citation_context: list[dict[str, Any]] = []
        for row in rows:
            citation_context.append(
                {
                    "id": row.get("id"),
                    "merchant_id": row.get("merchant_id", merchant_id),
                    "source": row.get("source"),
                    "source_row_id": row.get("source_row_id"),
                    "metric_name": row.get("metric_name"),
                    "value": _normalize_decimal(row.get("value", 0)),
                    "currency": row.get("currency"),
                    "dimensions": dict(row.get("dimensions") or {}),
                    "occurred_at": row.get("occurred_at"),
                    "synced_at": row.get("synced_at"),
                    "raw_payload": row.get("raw_payload"),
                    "citation_ref": f"[{row.get('source')}:{row.get('source_row_id')}]",
                }
            )

        log.info(
            "citation_context_built",
            source_row_count=len(citation_context),
        )

        return citation_context