from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qsl, urlparse

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


class ShopifyConnector(BaseConnector):
    """
    Reference implementation for Shopify ingestion.

    Responsibilities:
    - fetch raw Shopify orders
    - normalize them into provenance-safe rows
    - support pagination and retries
    - fail gracefully on partial bad payloads
    - never perform persistence or analytics logic
    """

    source_name = "shopify"

    def __init__(self) -> None:
        """Initialize Shopify API configuration and reusable HTTP settings."""

        settings = get_settings()
        self._shop_domain = settings.shopify_shop_domain.strip()
        self._access_token = settings.shopify_access_token.strip()
        self._api_version = settings.shopify_api_version
        self._base_url = f"https://{self._shop_domain}/admin/api/{self._api_version}"
        self._timeout = httpx.Timeout(30.0)
        self._headers = {
            "X-Shopify-Access-Token": self._access_token,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "d2c-ai-employee/1.0",
        }

    def _build_orders_url(self) -> str:
        """Return the Shopify orders endpoint URL."""

        return f"{self._base_url}/orders.json"

    def _build_order_admin_url(self, order_id: str) -> str:
        """Build a Shopify admin deep link for an order."""

        return f"https://{self._shop_domain}/admin/orders/{order_id}"

    def _parse_datetime(self, value: Any, field_name: str) -> datetime:
        """Parse an upstream ISO datetime value and normalize to UTC."""

        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty ISO datetime string")

        normalized_value = value.replace("Z", "+00:00")
        parsed_value = datetime.fromisoformat(normalized_value)

        if parsed_value.tzinfo is None:
            raise ValueError(f"{field_name} must be timezone-aware")

        return parsed_value.astimezone(timezone.utc)

    def _parse_decimal(self, value: Any, default: str = "0") -> Decimal:
        """Parse Shopify numeric payloads into Decimal safely."""

        if value is None:
            return Decimal(default)

        if isinstance(value, Decimal):
            return value

        return Decimal(str(value))

    def _build_provenance(
        self,
        order: dict[str, Any],
        source_row_id: str,
    ) -> Provenance:
        """Build provenance for a normalized Shopify row."""

        order_id = str(order.get("id", "unknown"))
        return Provenance(
            source=SourceType.SHOPIFY,
            source_row_id=source_row_id,
            source_url=self._build_order_admin_url(order_id),
            raw_payload=order,
        )

    def _base_dimensions(self, order: dict[str, Any]) -> dict[str, str]:
        """Build shared dimensions for all Shopify-derived rows."""

        customer = order.get("customer") or {}
        customer_email = customer.get("email") or order.get("email") or ""

        return {
            "order_id": str(order.get("id", "")),
            "customer_email": str(customer_email) if customer_email else "",
            "financial_status": str(order.get("financial_status", "")),
            "fulfillment_status": str(order.get("fulfillment_status", "")),
        }

    def _clean_dimensions(self, dimensions: dict[str, str]) -> dict[str, str]:
        """Remove blank dimension values while preserving explicit keys."""

        return {key: value for key, value in dimensions.items() if value}

    def _parse_link_header(self, link_header: str | None) -> str | None:
        """Extract the next-page URL from a Shopify Link header."""

        if not link_header:
            return None

        for segment in link_header.split(","):
            part = segment.strip()
            if 'rel="next"' not in part:
                continue

            start = part.find("<")
            end = part.find(">")
            if start == -1 or end == -1 or end <= start:
                continue

            return part[start + 1 : end]

        return None

    def _normalize_order_rows(self, merchant_id: str, order: dict[str, Any]) -> list[NormalizedRow]:
        """Normalize a single Shopify order into AI-ready metric rows."""

        order_id = str(order.get("id", ""))
        if not order_id:
            raise ValueError("order.id is required")

        occurred_at = self._parse_datetime(order.get("created_at"), "created_at")
        dimensions = self._clean_dimensions(self._base_dimensions(order))
        source_row_id = f"shopify_order_{order_id}"
        provenance = self._build_provenance(order=order, source_row_id=source_row_id)

        rows: list[NormalizedRow] = [
            NormalizedRow(
                merchant_id=merchant_id,
                metric_name=MetricName.REVENUE,
                value=self._parse_decimal(order.get("total_price")),
                currency=str(order.get("currency") or "INR"),
                dimensions=dimensions,
                occurred_at=occurred_at,
                provenance=provenance,
            ),
            NormalizedRow(
                merchant_id=merchant_id,
                metric_name=MetricName.ORDERS,
                value=Decimal("1"),
                currency="COUNT",
                dimensions=dimensions,
                occurred_at=occurred_at,
                provenance=self._build_provenance(order=order, source_row_id=source_row_id),
            ),
        ]

        for refund in order.get("refunds") or []:
            rows.extend(self._normalize_refund_rows(merchant_id=merchant_id, order=order, refund=refund))

        return rows

    def _normalize_refund_rows(
        self,
        merchant_id: str,
        order: dict[str, Any],
        refund: dict[str, Any],
    ) -> list[NormalizedRow]:
        """Normalize refund payloads into explicit refund metric rows."""

        order_id = str(order.get("id", "unknown"))
        refund_id = str(refund.get("id", "unknown"))
        refund_created_at = refund.get("created_at") or order.get("created_at")
        occurred_at = self._parse_datetime(refund_created_at, "refund.created_at")
        dimensions = self._clean_dimensions(
            {
                **self._base_dimensions(order),
                "refund_id": refund_id,
                "refund_note": str(refund.get("note", "")),
            }
        )
        source_row_id = f"shopify_order_{order_id}_refund_{refund_id}"
        refund_provenance = Provenance(
            source=SourceType.SHOPIFY,
            source_row_id=source_row_id,
            source_url=self._build_order_admin_url(order_id),
            raw_payload=order,
        )

        refund_total = Decimal("0")
        transactions = refund.get("transactions") or []
        for transaction in transactions:
            if str(transaction.get("kind", "")).lower() == "refund":
                refund_total += self._parse_decimal(transaction.get("amount"))

        if refund_total == 0:
            refund_total = self._parse_decimal(refund.get("total_amount"), default="0")

        return [
            NormalizedRow(
                merchant_id=merchant_id,
                metric_name=MetricName.REFUNDS,
                value=refund_total,
                currency=str(order.get("currency") or "INR"),
                dimensions=dimensions,
                occurred_at=occurred_at,
                provenance=refund_provenance,
            )
        ]

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
        page_number: int,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Fetch one page of Shopify orders and return the next-page URL if any."""

        log = self.get_logger(merchant_id).bind(page_count=page_number)
        response = await client.get(url, headers=self._headers, params=params)
        response.raise_for_status()

        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Shopify response body must be a JSON object")

        orders = payload.get("orders", [])
        if not isinstance(orders, list):
            raise ValueError("Shopify orders payload must be a list")

        next_url = self._parse_link_header(response.headers.get("Link"))

        log.info(
            "shopify_page_fetched",
            orders_processed=len(orders),
            next_page=bool(next_url),
        )

        return orders, next_url

    async def fetch(
        self,
        merchant_id: str,
        date_range: DateRange,
    ) -> list[NormalizedRow]:
        """Fetch Shopify orders, normalize them, and return provenance-safe rows."""

        log = self.get_logger(merchant_id)
        normalized_rows: list[NormalizedRow] = []
        page_count = 0
        orders_processed = 0
        failed_orders = 0

        current_url = self._build_orders_url()
        current_params: dict[str, Any] | None = {
            "status": "any",
            "limit": 250,
            "created_at_min": date_range.start.astimezone(timezone.utc).isoformat(),
            "created_at_max": date_range.end.astimezone(timezone.utc).isoformat(),
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                while current_url:
                    page_count += 1

                    try:
                        orders, next_url = await self._fetch_page(
                            client=client,
                            url=current_url,
                            params=current_params,
                            merchant_id=merchant_id,
                            page_number=page_count,
                        )
                    except Exception as exc:
                        log.error(
                            "shopify_page_failed",
                            page_count=page_count,
                            error=str(exc),
                            exc_info=True,
                        )
                        break

                    current_params = None
                    current_url = next_url

                    for order in orders:
                        try:
                            order_rows = self._normalize_order_rows(merchant_id, order)
                            normalized_rows.extend(order_rows)
                            orders_processed += 1
                        except Exception as exc:
                            failed_orders += 1
                            log.warning(
                                "shopify_order_skipped",
                                error=str(exc),
                                order_id=str(order.get("id", "unknown")),
                            )

        except Exception as exc:
            log.error(
                "shopify_fetch_failed",
                page_count=page_count,
                orders_processed=orders_processed,
                failed_orders=failed_orders,
                error=str(exc),
                exc_info=True,
            )

        validated_rows = self.validate_rows(normalized_rows)

        log.info(
            "shopify_fetch_completed",
            page_count=page_count,
            rows_generated=len(validated_rows),
            orders_processed=orders_processed,
            failed_orders=failed_orders,
        )

        return validated_rows

    async def health_check(self, merchant_id: str) -> bool:
        """Perform a lightweight credential and reachability check."""

        log = self.get_logger(merchant_id)
        url = f"{self._base_url}/shop.json"

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(url, headers=self._headers)
                healthy = response.status_code == 200

                log.info(
                    "shopify_health_check_completed",
                    status_code=response.status_code,
                    healthy=healthy,
                )

                return healthy
        except Exception as exc:
            log.warning(
                "shopify_health_check_failed",
                error=str(exc),
            )
            return False