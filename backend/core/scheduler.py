from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from time import perf_counter
from typing import AsyncIterator, Awaitable, Callable

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from backend.agents.ad_watchdog import AdWatchdogAgent
from backend.connectors.meta_ads import MetaAdsConnector
from backend.connectors.shiprocket import ShiprocketConnector
from backend.connectors.shopify import ShopifyConnector
from backend.core.config import get_settings
from backend.core.database import get_distinct_merchant_ids, save_agent_log, upsert_rows
from backend.core.logging import get_logger
from backend.repositories.metrics_repository import MetricsRepository
from backend.schema.models import DateRange


class RuntimeScheduler:
    """Thin APScheduler runtime for periodic operational jobs."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        self.scheduler = AsyncIOScheduler(timezone=timezone.utc)

        self.shopify_connector = ShopifyConnector()
        self.meta_connector = MetaAdsConnector()
        self.shiprocket_connector = ShiprocketConnector()
        self.metrics_repository = MetricsRepository()
        self.ad_watchdog = AdWatchdogAgent()

    def _job_logger(self, *, job_name: str, merchant_id: str | None = None) -> structlog.stdlib.BoundLogger:
        log = self.logger.bind(job_name=job_name)
        if merchant_id:
            log = log.bind(merchant_id=merchant_id)
        return log

    def _default_date_range(self) -> DateRange:
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=self.settings.default_sync_lookback_days)
        return DateRange(start=start, end=end)

    async def _safe_job_wrapper(self, job_name: str, job_fn: Callable[[], Awaitable[None]]) -> None:
        started_at = perf_counter()
        log = self._job_logger(job_name=job_name)
        try:
            log.info("scheduler_job_started")
            await job_fn()
            log.info("scheduler_job_completed", duration_ms=int((perf_counter() - started_at) * 1000))
        except Exception as exc:
            log.exception(
                "scheduler_job_failed",
                duration_ms=int((perf_counter() - started_at) * 1000),
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

    async def _run_connector_sync(
        self,
        *,
        job_name: str,
        connector: ShopifyConnector | MetaAdsConnector | ShiprocketConnector,
        merchant_id: str,
    ) -> None:
        started_at = perf_counter()
        log = self._job_logger(job_name=job_name, merchant_id=merchant_id)
        try:
            rows = await connector.fetch(merchant_id, self._default_date_range())
            rows_inserted = await upsert_rows(rows, merchant_id)
            log.info(
                "connector_sync_completed",
                duration_ms=int((perf_counter() - started_at) * 1000),
                rows_inserted=rows_inserted,
                source_name=connector.source_name,
                row_count=len(rows),
            )
        except Exception as exc:
            log.exception(
                "connector_sync_failed",
                duration_ms=int((perf_counter() - started_at) * 1000),
                source_name=connector.source_name,
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

    async def _run_agent(self, *, job_name: str, merchant_id: str) -> None:
        started_at = perf_counter()
        log = self._job_logger(job_name=job_name, merchant_id=merchant_id)
        try:
            result = await self.ad_watchdog.execute(merchant_id)
            agent_log = self.ad_watchdog.build_agent_log(merchant_id=merchant_id, result=result)
            await save_agent_log(agent_log)
            log.info(
                "agent_run_completed",
                duration_ms=int((perf_counter() - started_at) * 1000),
                recommendations=len(result.recommendations),
                citations=len(agent_log.citations),
                status=agent_log.status,
            )
        except Exception as exc:
            log.exception(
                "agent_run_failed",
                duration_ms=int((perf_counter() - started_at) * 1000),
                error_type=exc.__class__.__name__,
                error=str(exc),
            )

    async def sync_shopify(self) -> None:
        if not self.settings.enable_shopify_connector:
            self.logger.info("scheduler_job_skipped", job_name="sync_shopify", reason="connector_disabled")
            return
        merchant_ids = await get_distinct_merchant_ids()
        if not merchant_ids:
            self.logger.info("scheduler_job_skipped", job_name="sync_shopify", reason="no_merchants")
            return
        for mid in merchant_ids:
            await self._run_connector_sync(job_name="sync_shopify", connector=self.shopify_connector, merchant_id=mid)

    async def sync_meta_ads(self) -> None:
        if not self.settings.enable_meta_ads_connector:
            self.logger.info("scheduler_job_skipped", job_name="sync_meta_ads", reason="connector_disabled")
            return
        merchant_ids = await get_distinct_merchant_ids()
        if not merchant_ids:
            self.logger.info("scheduler_job_skipped", job_name="sync_meta_ads", reason="no_merchants")
            return
        for mid in merchant_ids:
            await self._run_connector_sync(job_name="sync_meta_ads", connector=self.meta_connector, merchant_id=mid)

    async def sync_shiprocket(self) -> None:
        if not self.settings.enable_shiprocket_connector:
            self.logger.info("scheduler_job_skipped", job_name="sync_shiprocket", reason="connector_disabled")
            return
        merchant_ids = await get_distinct_merchant_ids()
        if not merchant_ids:
            self.logger.info("scheduler_job_skipped", job_name="sync_shiprocket", reason="no_merchants")
            return
        for mid in merchant_ids:
            await self._run_connector_sync(job_name="sync_shiprocket", connector=self.shiprocket_connector, merchant_id=mid)

    async def run_ad_watchdog(self) -> None:
        merchant_ids = await get_distinct_merchant_ids()
        if not merchant_ids:
            self.logger.info("scheduler_job_skipped", job_name="run_ad_watchdog", reason="no_merchants")
            return
        for mid in merchant_ids:
            await self._run_agent(job_name="run_ad_watchdog", merchant_id=mid)

    async def _job_sync_shopify(self) -> None:
        await self._safe_job_wrapper("sync_shopify", self.sync_shopify)

    async def _job_sync_meta_ads(self) -> None:
        await self._safe_job_wrapper("sync_meta_ads", self.sync_meta_ads)

    async def _job_sync_shiprocket(self) -> None:
        await self._safe_job_wrapper("sync_shiprocket", self.sync_shiprocket)

    async def _job_run_ad_watchdog(self) -> None:
        await self._safe_job_wrapper("run_ad_watchdog", self.run_ad_watchdog)

    def register_jobs(self) -> None:
        sync_minutes = self.settings.connector_sync_interval_minutes
        watchdog_hours = self.settings.watchdog_interval_hours

        self.scheduler.add_job(self._job_sync_shopify, trigger="interval", minutes=sync_minutes,
                               id="sync_shopify", replace_existing=True, max_instances=1, coalesce=True)
        self.scheduler.add_job(self._job_sync_meta_ads, trigger="interval", minutes=sync_minutes,
                               id="sync_meta_ads", replace_existing=True, max_instances=1, coalesce=True)
        self.scheduler.add_job(self._job_sync_shiprocket, trigger="interval", minutes=sync_minutes,
                               id="sync_shiprocket", replace_existing=True, max_instances=1, coalesce=True)
        self.scheduler.add_job(self._job_run_ad_watchdog, trigger="interval", hours=watchdog_hours,
                               id="run_ad_watchdog", replace_existing=True, max_instances=1, coalesce=True)

    async def start(self) -> None:
        if not self.scheduler.running:
            self.register_jobs()
            self.scheduler.start()
        self.logger.info(
            "runtime_scheduler_started",
            connector_sync_interval_minutes=self.settings.connector_sync_interval_minutes,
            watchdog_interval_hours=self.settings.watchdog_interval_hours,
        )

    async def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        self.logger.info("runtime_scheduler_stopped")


runtime_scheduler = RuntimeScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await runtime_scheduler.start()
    try:
        yield
    finally:
        await runtime_scheduler.shutdown()
