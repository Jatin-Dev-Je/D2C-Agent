from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from backend.schema.models import DateRange, MetricName, MetricName as MN, SourceType


# ── Shopify connector ─────────────────────────────────────────────────────────

class TestShopifyConnector:
    _MERCHANT = "test-merchant-001"

    def _make_connector(self) -> object:
        from backend.connectors.shopify import ShopifyConnector
        with patch("backend.connectors.shopify.get_settings") as m:
            m.return_value = MagicMock(
                shopify_shop_domain="test.myshopify.com",
                shopify_access_token="shpat_test",
                shopify_api_version="2024-01",
            )
            return ShopifyConnector()

    def _order(self, **overrides: object) -> dict:
        base = {
            "id": 1001,
            "created_at": "2026-05-01T10:00:00Z",
            "total_price": "2500.00",
            "currency": "INR",
            "financial_status": "paid",
            "fulfillment_status": "fulfilled",
            "email": "customer@test.com",
            "refunds": [],
        }
        return {**base, **overrides}

    def test_source_name(self) -> None:
        assert self._make_connector().source_name == SourceType.SHOPIFY

    def test_normalizes_order_to_revenue_and_orders(self) -> None:
        rows = self._make_connector()._normalize_order_rows(self._MERCHANT, self._order())
        metric_names = {r.metric_name for r in rows}
        assert MetricName.REVENUE in metric_names
        assert MetricName.ORDERS in metric_names
        revenue = next(r for r in rows if r.metric_name == MetricName.REVENUE)
        assert revenue.value == pytest.approx(Decimal("2500.00"))
        assert revenue.provenance.source == SourceType.SHOPIFY

    def test_normalizes_refund_row(self) -> None:
        order = self._order(
            id=1002,
            financial_status="refunded",
            refunds=[{
                "id": 9001,
                "created_at": "2026-05-02T12:00:00Z",
                "transactions": [
                    {"id": "t1", "kind": "refund", "amount": "1000.00", "currency": "INR"},
                ],
            }],
        )
        rows = self._make_connector()._normalize_order_rows(self._MERCHANT, order)
        refund_rows = [r for r in rows if r.metric_name == MetricName.REFUNDS]
        assert len(refund_rows) == 1
        assert refund_rows[0].value == pytest.approx(Decimal("1000.00"))

    def test_null_price_treated_as_zero(self) -> None:
        rows = self._make_connector()._normalize_order_rows(
            self._MERCHANT, self._order(total_price=None)
        )
        revenue = next(r for r in rows if r.metric_name == MetricName.REVENUE)
        assert revenue.value == Decimal("0")

    def test_missing_order_id_raises(self) -> None:
        with pytest.raises((ValueError, KeyError, Exception)):
            self._make_connector()._normalize_order_rows(self._MERCHANT, self._order(id=""))


# ── Meta Ads connector ────────────────────────────────────────────────────────

class TestMetaAdsConnector:
    _MERCHANT = "test-merchant-002"
    _DEFAULT_DATE = datetime(2026, 5, 1, tzinfo=timezone.utc)

    def _make_connector(self) -> object:
        from backend.connectors.meta_ads import MetaAdsConnector
        with patch("backend.connectors.meta_ads.get_settings") as m:
            m.return_value = MagicMock(
                meta_access_token="test_token",
                meta_ad_account_id="123456789",
                meta_api_version="v19.0",
            )
            return MetaAdsConnector()

    def _insight(self, **overrides: object) -> dict:
        base = {
            "date_start": "2026-05-01",
            "campaign_id": "camp_001",
            "campaign_name": "Summer Sale",
            "spend": "1500.50",
            "impressions": "20000",
            "clicks": "350",
        }
        return {**base, **overrides}

    def test_source_name(self) -> None:
        assert self._make_connector().source_name == SourceType.META_ADS

    def test_normalizes_insight_to_three_metrics(self) -> None:
        rows = self._make_connector()._normalize_insight_rows(
            self._MERCHANT, self._insight(), self._DEFAULT_DATE
        )
        metric_names = {r.metric_name for r in rows}
        assert MetricName.AD_SPEND in metric_names
        assert MetricName.IMPRESSIONS in metric_names
        assert MetricName.CLICKS in metric_names

    def test_spend_value_correct(self) -> None:
        rows = self._make_connector()._normalize_insight_rows(
            self._MERCHANT, self._insight(spend="1500.50"), self._DEFAULT_DATE
        )
        spend = next(r for r in rows if r.metric_name == MetricName.AD_SPEND)
        assert spend.value == pytest.approx(Decimal("1500.50"), rel=Decimal("0.001"))

    def test_zero_spend_creates_zero_value_row(self) -> None:
        rows = self._make_connector()._normalize_insight_rows(
            self._MERCHANT, self._insight(spend="0", impressions="0", clicks="0"), self._DEFAULT_DATE
        )
        spend = next(r for r in rows if r.metric_name == MetricName.AD_SPEND)
        assert spend.value == Decimal("0")

    def test_missing_campaign_id_raises(self) -> None:
        with pytest.raises((ValueError, KeyError, Exception)):
            self._make_connector()._normalize_insight_rows(
                self._MERCHANT, self._insight(campaign_id=""), self._DEFAULT_DATE
            )


# ── Shiprocket connector ──────────────────────────────────────────────────────

class TestShiprocketConnector:
    _MERCHANT = "test-merchant-003"

    def _make_connector(self) -> object:
        from backend.connectors.shiprocket import ShiprocketConnector
        with patch("backend.connectors.shiprocket.get_settings") as m:
            m.return_value = MagicMock(
                shiprocket_email="test@test.com",
                shiprocket_password="testpass",
            )
            return ShiprocketConnector()

    def _order(self, **overrides: object) -> dict:
        base = {
            "id": 5001,
            "channel_order_id": "SR-1001",
            "created_at": "2026-05-01 10:00:00",
            "status": "DELIVERED",
            "status_code": 7,
            "freight_charges": 65.50,
            "total": 1500.0,
            "awb_code": "1234567890",
            "courier_name": "Delhivery",
            "billing_city": "Mumbai",
            "billing_state": "Maharashtra",
        }
        return {**base, **overrides}

    def test_source_name(self) -> None:
        assert self._make_connector().source_name == SourceType.SHIPROCKET

    def test_normalizes_delivered_order_to_shipping_cost(self) -> None:
        rows = self._make_connector()._normalize_order(self._MERCHANT, self._order())
        metric_names = {r.metric_name for r in rows}
        assert MetricName.SHIPPING_COST in metric_names
        assert MetricName.RTO not in metric_names
        cost = next(r for r in rows if r.metric_name == MetricName.SHIPPING_COST)
        assert cost.value == pytest.approx(Decimal("65.50"))
        assert cost.provenance.source == SourceType.SHIPROCKET

    def test_rto_order_produces_rto_row(self) -> None:
        rows = self._make_connector()._normalize_order(
            self._MERCHANT, self._order(status="RTO Delivered", status_code=10)
        )
        metric_names = {r.metric_name for r in rows}
        assert MetricName.SHIPPING_COST in metric_names
        assert MetricName.RTO in metric_names
        rto = next(r for r in rows if r.metric_name == MetricName.RTO)
        assert rto.value == Decimal("1")

    def test_zero_freight_returns_empty(self) -> None:
        rows = self._make_connector()._normalize_order(
            self._MERCHANT, self._order(freight_charges=0)
        )
        assert rows == []

    def test_missing_order_id_returns_empty(self) -> None:
        rows = self._make_connector()._normalize_order(
            self._MERCHANT, self._order(id="", channel_order_id="")
        )
        assert rows == []

    def test_dimensions_include_courier_and_city(self) -> None:
        rows = self._make_connector()._normalize_order(self._MERCHANT, self._order())
        cost = next(r for r in rows if r.metric_name == MetricName.SHIPPING_COST)
        assert cost.dimensions.get("courier_name") == "Delhivery"
        assert cost.dimensions.get("city") == "Mumbai"
