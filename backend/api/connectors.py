from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, status

from backend.connectors.meta_ads import MetaAdsConnector
from backend.connectors.shiprocket import ShiprocketConnector
from backend.connectors.shopify import ShopifyConnector
from backend.core.config import get_settings
from backend.core.database import upsert_rows
from backend.middleware.auth import get_merchant_id
from backend.middleware.rate_limit import check_rate_limit
from backend.schema.models import DateRange


router = APIRouter(prefix="/connectors", tags=["connectors"])
logger = structlog.get_logger(__name__)


async def _sync_connector(
    connector: ShopifyConnector | MetaAdsConnector | ShiprocketConnector,
    merchant_id: str,
    lookback_days: int,
) -> None:
    log = logger.bind(merchant_id=merchant_id, connector=connector.source_name)
    end = datetime.now(timezone.utc)
    date_range = DateRange(start=end - timedelta(days=lookback_days), end=end)
    try:
        rows = await connector.fetch(merchant_id, date_range)
        inserted = await upsert_rows(rows, merchant_id)
        log.info("manual_sync_completed", rows_fetched=len(rows), rows_inserted=inserted)
    except Exception as exc:
        log.exception("manual_sync_failed", error=str(exc))


@router.get("/health")
async def connector_health(
    merchant_id: str = Depends(get_merchant_id),
) -> dict[str, Any]:
    """Check health of all three connectors for the authenticated merchant."""
    await check_rate_limit(merchant_id)

    shopify = ShopifyConnector()
    meta = MetaAdsConnector()
    shiprocket = ShiprocketConnector()

    results = await asyncio.gather(
        shopify.health_check(merchant_id),
        meta.health_check(merchant_id),
        shiprocket.health_check(merchant_id),
        return_exceptions=True,
    )

    shopify_ok = results[0] is True
    meta_ok = results[1] is True
    shiprocket_ok = results[2] is True

    statuses = {
        "shopify":    {"healthy": shopify_ok,    "source": "shopify"},
        "meta_ads":   {"healthy": meta_ok,       "source": "meta_ads"},
        "shiprocket": {"healthy": shiprocket_ok, "source": "shiprocket"},
    }

    all_healthy = all(v["healthy"] for v in statuses.values())
    logger.bind(merchant_id=merchant_id).info("connector_health_checked", all_healthy=all_healthy)

    return {
        "merchant_id": merchant_id,
        "all_healthy": all_healthy,
        "connectors": statuses,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(
    background_tasks: BackgroundTasks,
    merchant_id: str = Depends(get_merchant_id),
) -> dict[str, Any]:
    """Trigger a background sync for all connectors for the authenticated merchant."""
    await check_rate_limit(merchant_id)
    settings = get_settings()
    lookback_days = settings.default_sync_lookback_days

    logger.bind(merchant_id=merchant_id).info("manual_sync_triggered", lookback_days=lookback_days)

    background_tasks.add_task(_sync_connector, ShopifyConnector(),    merchant_id, lookback_days)
    background_tasks.add_task(_sync_connector, MetaAdsConnector(),    merchant_id, lookback_days)
    background_tasks.add_task(_sync_connector, ShiprocketConnector(), merchant_id, lookback_days)

    return {
        "merchant_id": merchant_id,
        "status": "accepted",
        "connectors": ["shopify", "meta_ads", "shiprocket"],
        "lookback_days": lookback_days,
        "message": "Sync started in background. Check /connectors/health for status.",
    }
