from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from time import perf_counter
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.connectors.base import BaseConnector
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.schema.models import (
    DateRange,
    MetricName,
    NormalizedRow,
    Provenance,
    SourceType,
)


_BASE_URL = "https://apiv2.shiprocket.in/v1/external"

# Shiprocket status codes for RTO (return to origin)
_RTO_STATUS_CODES = {9, 10, 16, 17}   # RTO initiated / delivered / in transit

logger = get_logger(__name__)


class ShiprocketConnector(BaseConnector):
    """Sync shipping cost and RTO data from Shiprocket into normalized metric rows.

    Extracts per-shipment freight charges and flags returned orders (RTO)
    so the AI can calculate true fulfillment margins.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    @property
    def source_name(self) -> str:
        return SourceType.SHIPROCKET.value

    # ── Authentication ────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _authenticate(self) -> str:
        """Fetch a fresh JWT token from Shiprocket. Valid for ~24 hours."""
        import time
        with httpx.Client(timeout=30) as client:
            response = client.post(
                f"{_BASE_URL}/auth/local/register",
                json={
                    "email": self._settings.shiprocket_email,
                    "password": self._settings.shiprocket_password,
                },
            )
            response.raise_for_status()
            data = response.json()
            token = data.get("token", "")
            if not token:
                raise ValueError("Shiprocket auth returned no token")
            # Tokens are valid for ~24 h; refresh 30 min early to avoid expiry mid-sync
            self._token_expires_at = time.monotonic() + (23.5 * 3600)
            return token

    def _get_token(self) -> str:
        import time
        if not self._token or time.monotonic() >= self._token_expires_at:
            self._token = self._authenticate()
        return self._token

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_token()}",
            "Content-Type": "application/json",
        }

    # ── Data fetching ─────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _fetch_orders_page(self, page: int, from_date: str, to_date: str) -> dict[str, Any]:
        with httpx.Client(timeout=30) as client:
            response = client.get(
                f"{_BASE_URL}/orders",
                headers=self._headers(),
                params={
                    "per_page": 100,
                    "page": page,
                    "from": from_date,
                    "to": to_date,
                    "sort": "created_at",
                    "sort_order": "DESC",
                },
            )
            response.raise_for_status()
            return response.json()

    def _fetch_all_orders(self, date_range: DateRange) -> list[dict[str, Any]]:
        from_date = date_range.start.astimezone(timezone.utc).date().isoformat()
        to_date = date_range.end.astimezone(timezone.utc).date().isoformat()

        all_orders: list[dict[str, Any]] = []
        page = 1

        while True:
            payload = self._fetch_orders_page(page, from_date, to_date)
            orders = payload.get("data") or []
            all_orders.extend(orders)

            meta = payload.get("meta", {}).get("pagination", {})
            total_pages = int(meta.get("total_pages") or 1)
            if page >= total_pages or not orders:
                break
            page += 1

        return all_orders

    # ── Normalization ─────────────────────────────────────────────────────────

    def _parse_decimal(self, value: Any, default: str = "0") -> Decimal:
        try:
            return Decimal(str(value)) if value is not None else Decimal(default)
        except Exception:
            return Decimal(default)

    def _parse_datetime(self, value: Any) -> datetime:
        if not value:
            return datetime.now(timezone.utc)
        raw = str(value).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                dt = datetime.strptime(raw[:19], fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return datetime.now(timezone.utc)

    def _build_provenance(self, order: dict[str, Any], source_row_id: str) -> Provenance:
        return Provenance(
            source=SourceType.SHIPROCKET,
            source_row_id=source_row_id,
            source_url=None,
            raw_payload=order,
        )

    def _normalize_order(self, merchant_id: str, order: dict[str, Any]) -> list[NormalizedRow]:
        """Convert one Shiprocket order into SHIPPING_COST and optionally RTO rows."""
        order_id = str(order.get("id") or order.get("channel_order_id") or "")
        if not order_id:
            return []

        freight = self._parse_decimal(order.get("freight_charges"))
        if freight <= Decimal("0"):
            return []

        occurred_at = self._parse_datetime(order.get("created_at"))
        source_row_id = f"shiprocket_order_{order_id}"
        provenance = self._build_provenance(order, source_row_id)

        status_code = int(order.get("status_code") or 0)
        courier = str(order.get("courier_name") or "").strip()
        awb = str(order.get("awb_code") or "").strip()

        dimensions: dict[str, str] = {}
        if courier:
            dimensions["courier_name"] = courier
        if awb:
            dimensions["awb_code"] = awb
        if order.get("billing_city"):
            dimensions["city"] = str(order["billing_city"])
        if order.get("billing_state"):
            dimensions["state"] = str(order["billing_state"])

        rows: list[NormalizedRow] = [
            NormalizedRow(
                merchant_id=merchant_id,
                metric_name=MetricName.SHIPPING_COST,
                value=freight,
                currency="INR",
                dimensions=dimensions,
                occurred_at=occurred_at,
                provenance=provenance,
            )
        ]

        if status_code in _RTO_STATUS_CODES:
            rto_source_row_id = f"shiprocket_rto_{order_id}"
            rows.append(
                NormalizedRow(
                    merchant_id=merchant_id,
                    metric_name=MetricName.RTO,
                    value=Decimal("1"),
                    currency="COUNT",
                    dimensions={"rto_status_code": str(status_code), **dimensions},
                    occurred_at=occurred_at,
                    provenance=self._build_provenance(order, rto_source_row_id),
                )
            )

        return rows

    # ── Public interface ──────────────────────────────────────────────────────

    async def fetch(self, merchant_id: str, date_range: DateRange) -> list[NormalizedRow]:
        import asyncio

        log = self.get_logger(merchant_id)

        if not self._settings.shiprocket_email or not self._settings.shiprocket_password:
            log.warning("shiprocket_fetch_skipped", reason="credentials_not_configured")
            return []

        started_at = perf_counter()

        try:
            orders = await asyncio.to_thread(self._fetch_all_orders, date_range)
        except Exception as exc:
            log.exception("shiprocket_fetch_failed", error=str(exc))
            return []

        rows: list[NormalizedRow] = []
        skipped = 0

        for order in orders:
            try:
                normalized = self._normalize_order(merchant_id, order)
                rows.extend(normalized)
            except Exception as exc:
                skipped += 1
                log.warning(
                    "shiprocket_order_skipped",
                    order_id=order.get("id"),
                    error=str(exc),
                )

        validated = self.validate_rows(rows)
        duration_ms = int((perf_counter() - started_at) * 1000)
        log.info(
            "shiprocket_fetch_complete",
            orders_fetched=len(orders),
            rows_normalized=len(validated),
            skipped=skipped,
            duration_ms=duration_ms,
        )
        return validated

    async def health_check(self, merchant_id: str) -> bool:
        import asyncio

        if not self._settings.shiprocket_email or not self._settings.shiprocket_password:
            return False
        try:
            await asyncio.to_thread(self._authenticate)
            return True
        except Exception as exc:
            logger.warning("shiprocket_health_check_failed", error=str(exc))
            return False
