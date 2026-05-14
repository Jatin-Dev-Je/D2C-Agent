from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

import structlog

from backend.core.database import get_db
from backend.schema.models import MetricName, NormalizedRow


logger = structlog.get_logger(__name__)

METRIC_EVENTS_TABLE = "metric_events"

CAMPAIGN_METRICS: tuple[MetricName, ...] = (
    MetricName.AD_SPEND,
    MetricName.IMPRESSIONS,
    MetricName.CLICKS,
)


def _ensure_timezone_aware(value: datetime, field_name: str) -> datetime:
    """Validate timezone awareness and normalize to UTC."""

    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")

    return value.astimezone(timezone.utc)


def _ensure_date_range(start_date: datetime, end_date: datetime) -> tuple[datetime, datetime]:
    """Validate and normalize a datetime range for repository queries."""

    normalized_start = _ensure_timezone_aware(start_date, "start_date")
    normalized_end = _ensure_timezone_aware(end_date, "end_date")

    if normalized_start > normalized_end:
        raise ValueError("start_date cannot be after end_date")

    return normalized_start, normalized_end


def _normalize_decimal(value: Any) -> Decimal:
    """Convert database numeric payloads into Decimal safely."""

    if value is None:
        return Decimal("0")

    return Decimal(str(value))


def _clean_string_list(values: list[str]) -> list[str]:
    """Strip and filter blank string values."""

    return [value.strip() for value in values if value and value.strip()]


def _single_merchant_id(rows: list[NormalizedRow]) -> str:
    """Return the only merchant_id present in a batch of rows."""

    merchant_ids = {row.merchant_id for row in rows}

    if not merchant_ids:
        raise ValueError("insert_rows requires at least one row")

    if len(merchant_ids) != 1:
        raise ValueError("insert_rows requires a single merchant_id per batch")

    return next(iter(merchant_ids))


def _serialize_row(row: NormalizedRow) -> dict[str, Any]:
    """Serialize a normalized row into a database-safe payload."""

    return row.db_dict()


def _serialize_metric_row(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize a metric event row returned from the database."""

    dimensions = row.get("dimensions") or {}

    return {
        "id": row.get("id"),
        "merchant_id": row.get("merchant_id"),
        "source": row.get("source"),
        "source_row_id": row.get("source_row_id"),
        "metric_name": row.get("metric_name"),
        "value": _normalize_decimal(row.get("value")),
        "currency": row.get("currency"),
        "dimensions": dict(dimensions),
        "occurred_at": row.get("occurred_at"),
        "synced_at": row.get("synced_at"),
        "raw_payload": row.get("raw_payload"),
    }


async def _execute_query(query_factory: Callable[[], Any]) -> Any:
    """Run a blocking Supabase query in a worker thread."""

    return await asyncio.to_thread(query_factory)


async def insert_rows(rows: list[NormalizedRow]) -> int:
    """Insert normalized rows into metric_events idempotently."""

    if not rows:
        logger.bind(merchant_id="unknown").info(
            "metrics_insert_skipped",
            reason="empty_rows",
        )
        return 0

    merchant_id = _single_merchant_id(rows)
    log = logger.bind(merchant_id=merchant_id)
    payload = [_serialize_row(row) for row in rows]

    log.info(
        "metrics_insert_started",
        rows_attempted=len(payload),
    )

    try:
        response = await _execute_query(
            lambda: get_db()
            .table(METRIC_EVENTS_TABLE)
            .upsert(
                payload,
                on_conflict="merchant_id,source,source_row_id",
                ignore_duplicates=True,
            )
            .execute()
        )
    except Exception as exc:
        log.error(
            "metrics_insert_failed",
            rows_attempted=len(payload),
            error=str(exc),
            exc_info=True,
        )
        raise

    inserted_count = len(response.data or [])

    log.info(
        "metrics_insert_completed",
        rows_attempted=len(payload),
        rows_inserted=inserted_count,
    )

    return inserted_count


async def get_metric_sum(
    merchant_id: str,
    metric_name: MetricName,
    start_date: datetime,
    end_date: datetime,
) -> Decimal:
    """Aggregate a metric sum over a timezone-aware date range."""

    normalized_start, normalized_end = _ensure_date_range(start_date, end_date)
    log = logger.bind(merchant_id=merchant_id, metric_name=metric_name.value)

    try:
        response = await _execute_query(
            lambda: get_db()
            .table(METRIC_EVENTS_TABLE)
            .select("value")
            .eq("merchant_id", merchant_id)
            .eq("metric_name", metric_name.value)
            .gte("occurred_at", normalized_start.isoformat())
            .lte("occurred_at", normalized_end.isoformat())
            .execute()
        )
    except Exception as exc:
        log.error(
            "metric_sum_failed",
            start_date=normalized_start.isoformat(),
            end_date=normalized_end.isoformat(),
            error=str(exc),
            exc_info=True,
        )
        raise

    rows = response.data or []
    if not rows:
        log.info(
            "metric_sum_empty",
            start_date=normalized_start.isoformat(),
            end_date=normalized_end.isoformat(),
        )
        return Decimal("0")

    total = sum((_normalize_decimal(row.get("value")) for row in rows), Decimal("0"))

    log.info(
        "metric_sum_completed",
        start_date=normalized_start.isoformat(),
        end_date=normalized_end.isoformat(),
        rows_scanned=len(rows),
        total=str(total),
    )

    return total


async def get_metric_rows(
    merchant_id: str,
    metric_name: MetricName,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Return raw metric rows with provenance preserved."""

    normalized_start, normalized_end = _ensure_date_range(start_date, end_date)
    log = logger.bind(merchant_id=merchant_id, metric_name=metric_name.value)

    from backend.core.config import get_settings
    row_limit = get_settings().max_metric_rows

    try:
        response = await _execute_query(
            lambda: get_db()
            .table(METRIC_EVENTS_TABLE)
            .select("*")
            .eq("merchant_id", merchant_id)
            .eq("metric_name", metric_name.value)
            .gte("occurred_at", normalized_start.isoformat())
            .lte("occurred_at", normalized_end.isoformat())
            .order("occurred_at")
            .limit(row_limit)
            .execute()
        )
    except Exception as exc:
        log.error(
            "metric_rows_fetch_failed",
            start_date=normalized_start.isoformat(),
            end_date=normalized_end.isoformat(),
            error=str(exc),
            exc_info=True,
        )
        raise

    rows = [
        _serialize_metric_row(row)
        for row in (response.data or [])
    ]

    log.info(
        "metric_rows_fetched",
        start_date=normalized_start.isoformat(),
        end_date=normalized_end.isoformat(),
        rows_returned=len(rows),
    )

    return rows


async def compare_metric_periods(
    merchant_id: str,
    metric_name: MetricName,
    current_start: datetime,
    current_end: datetime,
    previous_start: datetime,
    previous_end: datetime,
) -> dict[str, Decimal]:
    """Compare metric performance across two periods."""

    current_value = await get_metric_sum(
        merchant_id=merchant_id,
        metric_name=metric_name,
        start_date=current_start,
        end_date=current_end,
    )
    previous_value = await get_metric_sum(
        merchant_id=merchant_id,
        metric_name=metric_name,
        start_date=previous_start,
        end_date=previous_end,
    )

    delta = current_value - previous_value

    if previous_value == 0:
        delta_percentage = Decimal("0")
    else:
        delta_percentage = (delta / previous_value) * Decimal("100")

    log = logger.bind(merchant_id=merchant_id, metric_name=metric_name.value)
    log.info(
        "metric_periods_compared",
        current_value=str(current_value),
        previous_value=str(previous_value),
        delta=str(delta),
        delta_percentage=str(delta_percentage),
    )

    return {
        "current_value": current_value,
        "previous_value": previous_value,
        "delta": delta,
        "delta_percentage": delta_percentage,
    }


async def get_campaign_performance(
    merchant_id: str,
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Aggregate Meta Ads campaign performance by campaign_id."""

    normalized_start, normalized_end = _ensure_date_range(start_date, end_date)
    log = logger.bind(merchant_id=merchant_id)

    try:
        response = await _execute_query(
            lambda: get_db()
            .table(METRIC_EVENTS_TABLE)
            .select("*")
            .eq("merchant_id", merchant_id)
            .eq("source", "meta_ads")
            .in_("metric_name", [metric.value for metric in CAMPAIGN_METRICS])
            .gte("occurred_at", normalized_start.isoformat())
            .lte("occurred_at", normalized_end.isoformat())
            .order("occurred_at")
            .execute()
        )
    except Exception as exc:
        log.error(
            "campaign_performance_failed",
            start_date=normalized_start.isoformat(),
            end_date=normalized_end.isoformat(),
            error=str(exc),
            exc_info=True,
        )
        raise

    campaign_totals: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "merchant_id": merchant_id,
            "campaign_id": "unknown",
            "campaign_name": "unknown",
            "spend": Decimal("0"),
            "impressions": Decimal("0"),
            "clicks": Decimal("0"),
            "source_row_ids": set(),
        }
    )

    for raw_row in response.data or []:
        dimensions = raw_row.get("dimensions") or {}
        campaign_id = str(dimensions.get("campaign_id", "unknown"))
        campaign_name = str(dimensions.get("campaign_name", "unknown"))
        metric_key = str(raw_row.get("metric_name", ""))
        row_value = _normalize_decimal(raw_row.get("value"))
        source_row_id = str(raw_row.get("source_row_id", "")).strip()

        campaign_entry = campaign_totals[campaign_id]
        campaign_entry["campaign_id"] = campaign_id
        campaign_entry["campaign_name"] = campaign_name
        if source_row_id:
            campaign_entry["source_row_ids"].add(source_row_id)

        if metric_key == MetricName.AD_SPEND.value:
            campaign_entry["spend"] += row_value
        elif metric_key == MetricName.IMPRESSIONS.value:
            campaign_entry["impressions"] += row_value
        elif metric_key == MetricName.CLICKS.value:
            campaign_entry["clicks"] += row_value

    results = sorted(
        (
            {**entry, "source_row_ids": sorted(entry["source_row_ids"])}
            for entry in campaign_totals.values()
        ),
        key=lambda item: item["spend"],
        reverse=True,
    )

    log.info(
        "campaign_performance_fetched",
        start_date=normalized_start.isoformat(),
        end_date=normalized_end.isoformat(),
        campaign_count=len(results),
    )

    return results


async def get_rows_by_source_ids(
    merchant_id: str,
    source_row_ids: list[str],
) -> list[dict[str, Any]]:
    """Return exact rows used for citation grounding."""

    cleaned_source_row_ids = _clean_string_list(source_row_ids)
    log = logger.bind(merchant_id=merchant_id)

    if not cleaned_source_row_ids:
        log.info(
            "source_rows_lookup_skipped",
            reason="empty_source_row_ids",
        )
        return []

    try:
        response = await _execute_query(
            lambda: get_db()
            .table(METRIC_EVENTS_TABLE)
            .select("*")
            .eq("merchant_id", merchant_id)
            .in_("source_row_id", cleaned_source_row_ids)
            .order("occurred_at")
            .execute()
        )
    except Exception as exc:
        log.error(
            "source_rows_fetch_failed",
            source_row_ids=cleaned_source_row_ids,
            error=str(exc),
            exc_info=True,
        )
        raise

    rows = [
        _serialize_metric_row(row)
        for row in (response.data or [])
    ]

    log.info(
        "source_rows_fetched",
        source_row_count=len(rows),
    )

    return rows


class MetricsRepository:
    """
    Thin orchestration-friendly repository wrapper.

    The module-level functions remain available for direct reuse, while this
    class gives services a stable dependency boundary for future backend swaps.
    """

    async def insert_rows(self, rows: list[NormalizedRow]) -> int:
        """Insert normalized rows into metric_events idempotently."""

        return await insert_rows(rows)

    async def get_metric_sum(
        self,
        merchant_id: str,
        metric_name: MetricName,
        start_date: datetime,
        end_date: datetime,
    ) -> Decimal:
        """Aggregate a metric sum over a timezone-aware date range."""

        return await get_metric_sum(
            merchant_id=merchant_id,
            metric_name=metric_name,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_metric_rows(
        self,
        merchant_id: str,
        metric_name: MetricName,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Return raw metric rows with provenance preserved."""

        return await get_metric_rows(
            merchant_id=merchant_id,
            metric_name=metric_name,
            start_date=start_date,
            end_date=end_date,
        )

    async def compare_metric_periods(
        self,
        merchant_id: str,
        metric_name: MetricName,
        current_start: datetime,
        current_end: datetime,
        previous_start: datetime,
        previous_end: datetime,
    ) -> dict[str, Decimal]:
        """Compare metric performance across two periods."""

        return await compare_metric_periods(
            merchant_id=merchant_id,
            metric_name=metric_name,
            current_start=current_start,
            current_end=current_end,
            previous_start=previous_start,
            previous_end=previous_end,
        )

    async def get_campaign_performance(
        self,
        merchant_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict[str, Any]]:
        """Aggregate Meta Ads campaign performance by campaign_id."""

        return await get_campaign_performance(
            merchant_id=merchant_id,
            start_date=start_date,
            end_date=end_date,
        )

    async def get_rows_by_source_ids(
        self,
        merchant_id: str,
        source_row_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Return exact rows used for citation grounding."""

        return await get_rows_by_source_ids(
            merchant_id=merchant_id,
            source_row_ids=source_row_ids,
        )