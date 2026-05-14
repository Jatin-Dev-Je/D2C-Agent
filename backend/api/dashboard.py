from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

import structlog
from fastapi import APIRouter, Depends

from backend.core.database import get_agent_logs
from backend.middleware.auth import get_merchant_id
from backend.middleware.rate_limit import check_rate_limit
from backend.repositories.metrics_repository import MetricsRepository
from backend.schema.models import MetricName
from backend.services.metrics_service import MetricsService


router = APIRouter(prefix="/dashboard", tags=["dashboard"])
logger = structlog.get_logger(__name__)


@router.get("")
async def get_dashboard(
    merchant_id: str = Depends(get_merchant_id),
) -> dict[str, Any]:
    """Return a 30-day overview: key metrics, recent agent logs."""

    await check_rate_limit(merchant_id)
    log = logger.bind(merchant_id=merchant_id)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)

    service = MetricsService(repository=MetricsRepository())

    revenue_task = service.get_metric_summary(
        merchant_id=merchant_id,
        metric_name=MetricName.REVENUE,
        start_date=start,
        end_date=end,
    )
    orders_task = service.get_metric_summary(
        merchant_id=merchant_id,
        metric_name=MetricName.ORDERS,
        start_date=start,
        end_date=end,
    )
    ad_spend_task = service.get_metric_summary(
        merchant_id=merchant_id,
        metric_name=MetricName.AD_SPEND,
        start_date=start,
        end_date=end,
    )
    roas_task = service.get_roas_summary(
        merchant_id=merchant_id,
        start_date=start,
        end_date=end,
    )
    agent_logs_task = get_agent_logs(merchant_id=merchant_id, limit=5, offset=0)

    import asyncio
    revenue, orders, ad_spend, roas, recent_logs = await asyncio.gather(
        revenue_task,
        orders_task,
        ad_spend_task,
        roas_task,
        agent_logs_task,
        return_exceptions=True,
    )

    def _safe_decimal(result: Any, key: str) -> str:
        if isinstance(result, Exception) or not isinstance(result, dict):
            return "0"
        val = result.get(key, Decimal("0"))
        return str(val)

    log.info("dashboard_built", merchant_id=merchant_id)

    return {
        "merchant_id": merchant_id,
        "period": {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "days": 30,
        },
        "metrics": {
            "revenue_inr": _safe_decimal(revenue, "total"),
            "orders": _safe_decimal(orders, "total"),
            "ad_spend_inr": _safe_decimal(ad_spend, "total"),
            "roas": _safe_decimal(roas, "roas"),
        },
        "recent_agent_logs": recent_logs if isinstance(recent_logs, list) else [],
        "generated_at": end.isoformat(),
    }
