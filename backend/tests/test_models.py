from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from backend.schema.models import (
    AgentRunLog,
    CitationTrace,
    CitedValue,
    ConnectorSyncResult,
    DateRange,
    MetricName,
    NormalizedRow,
    Provenance,
    SourceType,
    normalize_decimal,
)


# ── normalize_decimal ─────────────────────────────────────────────────────────

def test_normalize_decimal_rounds_half_up():
    assert normalize_decimal("1.555") == Decimal("1.56")
    assert normalize_decimal("1.554") == Decimal("1.55")


def test_normalize_decimal_from_int():
    assert normalize_decimal(100) == Decimal("100.00")


def test_normalize_decimal_from_float():
    result = normalize_decimal(1.1)
    assert result == Decimal("1.10")


# ── DateRange ─────────────────────────────────────────────────────────────────

def test_date_range_valid():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 1, 31, tzinfo=timezone.utc)
    dr = DateRange(start=start, end=end)
    assert dr.start == start
    assert dr.end == end


def test_date_range_rejects_naive_start():
    with pytest.raises(ValueError, match="timezone-aware"):
        DateRange(start=datetime(2024, 1, 1), end=datetime(2024, 1, 31, tzinfo=timezone.utc))


def test_date_range_rejects_naive_end():
    with pytest.raises(ValueError, match="timezone-aware"):
        DateRange(start=datetime(2024, 1, 1, tzinfo=timezone.utc), end=datetime(2024, 1, 31))


def test_date_range_rejects_inverted_range():
    with pytest.raises(ValueError, match="cannot be after"):
        DateRange(
            start=datetime(2024, 1, 31, tzinfo=timezone.utc),
            end=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )


# ── Provenance ────────────────────────────────────────────────────────────────

def test_provenance_valid():
    p = Provenance(source=SourceType.SHOPIFY, source_row_id="shopify_order_123")
    assert p.source == SourceType.SHOPIFY
    assert p.source_row_id == "shopify_order_123"
    assert p.synced_at.tzinfo is not None


def test_provenance_rejects_blank_source_row_id():
    with pytest.raises(ValueError, match="source_row_id cannot be empty"):
        Provenance(source=SourceType.SHOPIFY, source_row_id="   ")


def test_provenance_rejects_naive_synced_at():
    with pytest.raises(ValueError, match="timezone-aware"):
        Provenance(
            source=SourceType.SHOPIFY,
            source_row_id="row_1",
            synced_at=datetime(2024, 1, 1),
        )


def test_provenance_normalizes_synced_at_to_utc():
    from datetime import timedelta, timezone as tz
    ist = tz(timedelta(hours=5, minutes=30))
    synced_at_ist = datetime(2024, 1, 1, 12, 0, tzinfo=ist)
    p = Provenance(source=SourceType.META_ADS, source_row_id="row_1", synced_at=synced_at_ist)
    assert p.synced_at.tzinfo == timezone.utc
    assert p.synced_at.hour == 6  # 12:00 IST = 06:30 UTC → hour is 6


def test_provenance_summary():
    p = Provenance(source=SourceType.SHOPIFY, source_row_id="shopify_order_123")
    assert p.summary() == "shopify:shopify_order_123"


# ── NormalizedRow ─────────────────────────────────────────────────────────────

def _make_provenance(source_row_id: str = "row_1", source: SourceType = SourceType.SHOPIFY) -> Provenance:
    return Provenance(source=source, source_row_id=source_row_id)


def _make_row(**kwargs) -> NormalizedRow:
    defaults = dict(
        merchant_id="merchant-123",
        metric_name=MetricName.REVENUE,
        value=Decimal("1000.00"),
        occurred_at=datetime(2024, 1, 15, tzinfo=timezone.utc),
        provenance=_make_provenance(),
    )
    defaults.update(kwargs)
    return NormalizedRow(**defaults)


def test_normalized_row_valid():
    row = _make_row()
    assert row.merchant_id == "merchant-123"
    assert row.metric_name == MetricName.REVENUE
    assert row.value == Decimal("1000.00")


def test_normalized_row_rejects_blank_merchant_id():
    with pytest.raises(ValueError, match="merchant_id cannot be empty"):
        _make_row(merchant_id="   ")


def test_normalized_row_rejects_naive_occurred_at():
    with pytest.raises(ValueError, match="timezone-aware"):
        _make_row(occurred_at=datetime(2024, 1, 15))


def test_normalized_row_normalizes_decimal():
    row = _make_row(value=Decimal("100.555"))
    assert row.value == Decimal("100.56")


def test_normalized_row_db_dict_shape():
    row = _make_row()
    d = row.db_dict()
    assert d["source"] == "shopify"
    assert d["metric_name"] == "revenue"
    assert d["value"] == str(row.value)
    assert d["merchant_id"] == "merchant-123"


def test_normalized_row_citation_ref():
    row = _make_row(provenance=_make_provenance("shopify_order_99"))
    assert row.citation_ref() == "[shopify:shopify_order_99]"


# ── CitedValue ────────────────────────────────────────────────────────────────

def test_cited_value_valid():
    cv = CitedValue(
        value=Decimal("500.00"),
        currency="INR",
        metric_name="revenue",
        source_row_ids=["shopify_order_1", "shopify_order_2"],
        source=SourceType.SHOPIFY,
    )
    assert len(cv.source_row_ids) == 2


def test_cited_value_rejects_empty_source_row_ids():
    with pytest.raises(ValueError, match="source_row_ids cannot be empty"):
        CitedValue(
            value=Decimal("500.00"),
            currency="INR",
            metric_name="revenue",
            source_row_ids=[],
            source=SourceType.SHOPIFY,
        )


def test_cited_value_rejects_all_blank_source_row_ids():
    with pytest.raises(ValueError, match="source_row_ids cannot be blank"):
        CitedValue(
            value=Decimal("500.00"),
            currency="INR",
            metric_name="revenue",
            source_row_ids=["   ", ""],
            source=SourceType.SHOPIFY,
        )


def test_cited_value_strips_whitespace_from_row_ids():
    cv = CitedValue(
        value=Decimal("100"),
        currency="INR",
        metric_name="revenue",
        source_row_ids=["  row_1  ", "row_2"],
        source=SourceType.SHOPIFY,
    )
    assert cv.source_row_ids == ["row_1", "row_2"]


# ── CitationTrace ─────────────────────────────────────────────────────────────

def test_citation_trace_valid():
    ct = CitationTrace(
        metric_name="revenue",
        operation="get_metric_summary",
        source_row_ids=["row_1", "row_2"],
    )
    assert ct.generated_at.tzinfo is not None


# ── AgentRunLog ───────────────────────────────────────────────────────────────

def test_agent_run_log_valid():
    log = AgentRunLog(
        agent_name="ad_watchdog",
        merchant_id="merchant-123",
        observation="Spend spike detected",
        reasoning="Current spend is 2x previous period",
        proposed_action="Reduce daily budget by 30%",
        estimated_saving_inr=Decimal("5000.00"),
        citations=["meta_campaign_1_2024-01-01_spend"],
        executed=False,
    )
    assert log.status == "proposed"
    assert log.executed is False


def test_agent_run_log_rejects_executed_true():
    with pytest.raises(ValueError, match="executed must always remain False"):
        AgentRunLog(
            agent_name="ad_watchdog",
            merchant_id="merchant-123",
            observation="obs",
            reasoning="reason",
            proposed_action="action",
            executed=True,
        )


def test_agent_run_log_normalizes_saving():
    log = AgentRunLog(
        agent_name="ad_watchdog",
        merchant_id="merchant-123",
        observation="obs",
        reasoning="reason",
        proposed_action="action",
        estimated_saving_inr=Decimal("999.999"),
    )
    assert log.estimated_saving_inr == Decimal("1000.00")


# ── ConnectorSyncResult ───────────────────────────────────────────────────────

def test_connector_sync_result_valid():
    now = datetime.now(timezone.utc)
    result = ConnectorSyncResult(
        connector_name="shopify",
        merchant_id="merchant-123",
        rows_fetched=100,
        rows_inserted=98,
        failed_rows=2,
        duration_ms=1500,
        started_at=now,
        completed_at=now,
        success=True,
    )
    assert result.rows_inserted == 98


# ── SourceType / MetricName enums ─────────────────────────────────────────────

def test_source_type_values():
    assert SourceType.SHOPIFY.value == "shopify"
    assert SourceType.META_ADS.value == "meta_ads"
    assert SourceType.SHIPROCKET.value == "shiprocket"


def test_metric_name_all_defined():
    expected = {
        "revenue", "orders", "ad_spend", "roas", "impressions",
        "clicks", "cogs", "refunds", "avg_order_value", "shipping_cost", "rto",
    }
    actual = {m.value for m in MetricName}
    assert actual == expected
