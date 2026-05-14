from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
import structlog
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.connectors.base import BaseConnector
from backend.core.config import get_settings
from backend.schema.models import (
    DateRange,
    MetricName,
    NormalizedRow,
    Provenance,
    SourceType,
)


logger = structlog.get_logger(__name__)


class MetaAdsConnector(BaseConnector):
    """
    Reference implementation for Meta Ads ingestion.

    Responsibilities:
    - fetch campaign insights from Meta Graph API
    - normalize spend, impressions, and clicks into rows
    - preserve provenance exactly
    - remain deterministic and retry-safe
    - never perform analytics or decision logic
    """

    source_name = "meta_ads"

    def __init__(self) -> None:
        """Initialize Meta Graph API configuration and reusable HTTP settings."""

        settings = get_settings()
        self._access_token = settings.meta_access_token.strip()
        self._ad_account_id = settings.meta_ad_account_id.strip()
        self._api_version = settings.meta_api_version
        self._base_url = f"https://graph.facebook.com/{self._api_version}"
        self._timeout = httpx.Timeout(30.0)
        self._headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "d2c-ai-employee/1.0",
        }

    def _parse_datetime(self, value: Any, field_name: str) -> datetime:
        """Parse a Meta API date string and normalize it to UTC."""

        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty ISO date string")

        parsed_value = datetime.fromisoformat(value.strip())
        if parsed_value.tzinfo is None:
            parsed_value = parsed_value.replace(tzinfo=timezone.utc)

        return parsed_value.astimezone(timezone.utc)

    def _parse_decimal(self, value: Any, default: str = "0") -> Decimal:
        """Parse Meta payload numeric values into Decimal safely."""

        if value is None:
            return Decimal(default)

        if isinstance(value, Decimal):
            return value

        return Decimal(str(value))

    def _build_provenance(
        self,
        insight: dict[str, Any],
        source_row_id: str,
    ) -> Provenance:
        """Build provenance for a normalized Meta Ads row."""

        return Provenance(
            source=SourceType.META_ADS,
            source_row_id=source_row_id,
            raw_payload=insight,
        )

    def _normalize_dimensions(self, insight: dict[str, Any]) -> dict[str, str]:
        """Normalize shared campaign dimensions for all generated rows."""

        dimensions = {
            "campaign_id": str(insight.get("campaign_id", "unknown")),
            "campaign_name": str(insight.get("campaign_name", "unknown")),
        }
        return {key: value for key, value in dimensions.items() if value}

    def _normalize_insight_rows(
        self,
        merchant_id: str,
        insight: dict[str, Any],
        default_date: datetime,
    ) -> list[NormalizedRow]:
        """Normalize a single campaign insight into AI-ready metric rows."""

        campaign_id = str(insight.get("campaign_id", ""))
        if not campaign_id:
            raise ValueError("campaign_id is required")

        date_start = insight.get("date_start") or default_date.date().isoformat()
        occurred_at = self._parse_datetime(date_start, "date_start")
        dimensions = self._normalize_dimensions(insight)
        # Each metric gets its own source_row_id so all three survive the
        # unique(merchant_id, source, source_row_id) constraint on upsert.
        base_id = f"meta_campaign_{campaign_id}_{date_start}"

        rows: list[NormalizedRow] = [
            NormalizedRow(
                merchant_id=merchant_id,
                metric_name=MetricName.AD_SPEND,
                value=self._parse_decimal(insight.get("spend")),
                currency="INR",
                dimensions=dimensions,
                occurred_at=occurred_at,
                provenance=self._build_provenance(insight=insight, source_row_id=f"{base_id}_spend"),
            ),
            NormalizedRow(
                merchant_id=merchant_id,
                metric_name=MetricName.IMPRESSIONS,
                value=self._parse_decimal(insight.get("impressions")),
                currency="COUNT",
                dimensions=dimensions,
                occurred_at=occurred_at,
                provenance=self._build_provenance(insight=insight, source_row_id=f"{base_id}_impressions"),
            ),
            NormalizedRow(
                merchant_id=merchant_id,
                metric_name=MetricName.CLICKS,
                value=self._parse_decimal(insight.get("clicks")),
                currency="COUNT",
                dimensions=dimensions,
                occurred_at=occurred_at,
                provenance=self._build_provenance(insight=insight, source_row_id=f"{base_id}_clicks"),
            ),
        ]

        return rows

    def _build_time_range(self, date_range: DateRange) -> str:
        """Build the Meta Graph API time_range parameter."""

        since = date_range.start.astimezone(timezone.utc).date().isoformat()
        until = date_range.end.astimezone(timezone.utc).date().isoformat()
        return f'{{"since":"{since}","until":"{until}"}}'

    def _build_insights_url(self) -> str:
        """Build the Meta insights endpoint URL."""

        return f"{self._base_url}/act_{self._ad_account_id}/insights"

    def _parse_next_page_url(self, payload: dict[str, Any]) -> str | None:
        """Extract the next page URL from Graph API paging metadata."""

        paging = payload.get("paging")
        if not isinstance(paging, dict):
            return None

        next_url = paging.get("next")
        if isinstance(next_url, str) and next_url.strip():
            return next_url

        return None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, TimeoutError, ValueError)),
        reraise=True,
    )
    async def _fetch_page(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict[str, Any] | None,
        merchant_id: str,
        page_count: int,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Fetch one Meta Ads insights page and return the next page URL if present."""

        log = self.get_logger(merchant_id).bind(page_count=page_count)
        response = await client.get(url, params=params, headers=self._headers)
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Meta Ads response body must be a JSON object")

        insights = payload.get("data", [])
        if not isinstance(insights, list):
            raise ValueError("Meta Ads insights payload must be a list")

        next_url = self._parse_next_page_url(payload)

        log.info(
            "meta_ads_page_fetched",
            campaign_count=len(insights),
            next_page=bool(next_url),
        )

        return insights, next_url

    async def fetch(
        self,
        merchant_id: str,
        date_range: DateRange,
    ) -> list[NormalizedRow]:
        """Fetch campaign insights, normalize them, and return provenance-safe rows."""

        log = self.get_logger(merchant_id)
        normalized_rows: list[NormalizedRow] = []
        page_count = 0
        campaign_count = 0
        failed_campaigns = 0

        current_url = self._build_insights_url()
        current_params: dict[str, Any] | None = {
            "fields": "campaign_id,campaign_name,spend,impressions,clicks,date_start",
            "level": "campaign",
            "limit": 500,
            "time_range": self._build_time_range(date_range),
            "access_token": self._access_token,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                while current_url:
                    page_count += 1

                    try:
                        insights, next_url = await self._fetch_page(
                            client=client,
                            url=current_url,
                            params=current_params,
                            merchant_id=merchant_id,
                            page_count=page_count,
                        )
                    except Exception as exc:
                        log.error(
                            "meta_ads_page_failed",
                            page_count=page_count,
                            error=str(exc),
                            exc_info=True,
                        )
                        break

                    current_params = None
                    current_url = next_url

                    for insight in insights:
                        try:
                            insight_rows = self._normalize_insight_rows(
                                merchant_id=merchant_id,
                                insight=insight,
                                default_date=date_range.start,
                            )
                            normalized_rows.extend(insight_rows)
                            campaign_count += 1
                        except Exception as exc:
                            failed_campaigns += 1
                            log.warning(
                                "meta_ads_campaign_skipped",
                                error=str(exc),
                                campaign_id=str(insight.get("campaign_id", "unknown")),
                            )

        except Exception as exc:
            log.error(
                "meta_ads_fetch_failed",
                page_count=page_count,
                campaign_count=campaign_count,
                failed_campaigns=failed_campaigns,
                error=str(exc),
                exc_info=True,
            )

        validated_rows = self.validate_rows(normalized_rows)

        log.info(
            "meta_ads_fetch_completed",
            page_count=page_count,
            campaign_count=campaign_count,
            rows_generated=len(validated_rows),
            failed_campaigns=failed_campaigns,
        )

        return validated_rows

    async def health_check(self, merchant_id: str) -> bool:
        """Perform a lightweight Graph API health check."""

        log = self.get_logger(merchant_id)
        url = f"{self._base_url}/me"
        params = {"access_token": self._access_token, "fields": "id"}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, params=params, headers=self._headers)
                healthy = response.status_code == 200

                log.info(
                    "meta_ads_health_check_completed",
                    status_code=response.status_code,
                    healthy=healthy,
                )

                return healthy
        except Exception as exc:
            log.warning(
                "meta_ads_health_check_failed",
                error=str(exc),
            )
            return False