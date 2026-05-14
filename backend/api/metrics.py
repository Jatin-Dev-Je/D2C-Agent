from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.middleware.auth import get_merchant_id
from backend.middleware.rate_limit import check_rate_limit
from backend.repositories.metrics_repository import MetricsRepository
from backend.schema.models import MetricName
from backend.services.metrics_service import MetricsService


router = APIRouter(prefix="/metrics", tags=["metrics"])
logger = structlog.get_logger(__name__)

_METRIC_NAMES = [m.value for m in MetricName]


def _parse_date(value: str, field_name: str) -> datetime:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{field_name} must be a valid ISO 8601 datetime",
        )


def _get_metrics_service() -> MetricsService:
    return MetricsService(repository=MetricsRepository())


@router.get("/summary")
async def get_metric_summary(
    metric_name: str = Query(..., description=f"One of: {_METRIC_NAMES}"),
    start_date: str = Query(..., description="ISO 8601 datetime"),
    end_date: str = Query(..., description="ISO 8601 datetime"),
    merchant_id: str = Depends(get_merchant_id),
) -> dict[str, Any]:
    """Return aggregated metric total for the authenticated merchant over a date range."""

    await check_rate_limit(merchant_id)

    try:
        metric = MetricName(metric_name)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"metric_name must be one of: {_METRIC_NAMES}",
        )

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date")

    service = _get_metrics_service()
    result = await service.get_metric_summary(
        merchant_id=merchant_id,
        metric_name=metric,
        start_date=start,
        end_date=end,
    )

    return {
        **result,
        "total": str(result["total"]),
        "start_date": result["start_date"].isoformat(),
        "end_date": result["end_date"].isoformat(),
    }


@router.get("/compare")
async def compare_metric_periods(
    metric_name: str = Query(..., description=f"One of: {_METRIC_NAMES}"),
    current_start: str = Query(...),
    current_end: str = Query(...),
    previous_start: str = Query(...),
    previous_end: str = Query(...),
    merchant_id: str = Depends(get_merchant_id),
) -> dict[str, Any]:
    """Compare a metric between two date ranges."""

    await check_rate_limit(merchant_id)

    try:
        metric = MetricName(metric_name)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"metric_name must be one of: {_METRIC_NAMES}",
        )

    service = _get_metrics_service()
    result = await service.compare_metric_periods(
        merchant_id=merchant_id,
        metric_name=metric,
        current_start=_parse_date(current_start, "current_start"),
        current_end=_parse_date(current_end, "current_end"),
        previous_start=_parse_date(previous_start, "previous_start"),
        previous_end=_parse_date(previous_end, "previous_end"),
    )

    return {
        **result,
        "current_value": str(result["current_value"]),
        "previous_value": str(result["previous_value"]),
        "delta": str(result["delta"]),
        "delta_percentage": str(result["delta_percentage"]),
        "current_start": result["current_start"].isoformat(),
        "current_end": result["current_end"].isoformat(),
        "previous_start": result["previous_start"].isoformat(),
        "previous_end": result["previous_end"].isoformat(),
    }


@router.get("/roas")
async def get_roas_summary(
    start_date: str = Query(..., description="ISO 8601 datetime"),
    end_date: str = Query(..., description="ISO 8601 datetime"),
    merchant_id: str = Depends(get_merchant_id),
) -> dict[str, Any]:
    """Return grounded ROAS summary for the authenticated merchant."""

    await check_rate_limit(merchant_id)

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date")

    service = _get_metrics_service()
    result = await service.get_roas_summary(
        merchant_id=merchant_id,
        start_date=start,
        end_date=end,
    )

    return {
        **result,
        "revenue": str(result["revenue"]),
        "ad_spend": str(result["ad_spend"]),
        "roas": str(result["roas"]),
        "start_date": result["start_date"].isoformat(),
        "end_date": result["end_date"].isoformat(),
    }


@router.get("/campaigns")
async def get_campaign_performance(
    start_date: str = Query(..., description="ISO 8601 datetime"),
    end_date: str = Query(..., description="ISO 8601 datetime"),
    limit: int = Query(default=100, ge=1, le=500),
    merchant_id: str = Depends(get_merchant_id),
) -> dict[str, Any]:
    """Return campaign-level performance aggregated from Meta Ads data."""

    await check_rate_limit(merchant_id)

    start = _parse_date(start_date, "start_date")
    end = _parse_date(end_date, "end_date")

    service = _get_metrics_service()
    result = await service.get_campaign_performance_summary(
        merchant_id=merchant_id,
        start_date=start,
        end_date=end,
    )

    campaigns = result.get("campaigns", [])[:limit]
    serialized_campaigns = [
        {
            **c,
            "spend": str(c["spend"]),
            "impressions": str(c["impressions"]),
            "clicks": str(c["clicks"]),
        }
        for c in campaigns
    ]

    return {
        "merchant_id": merchant_id,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "campaign_count": result.get("campaign_count", 0),
        "total_spend": str(result.get("total_spend", "0")),
        "total_clicks": str(result.get("total_clicks", "0")),
        "total_impressions": str(result.get("total_impressions", "0")),
        "campaigns": serialized_campaigns,
        "limit": limit,
    }
