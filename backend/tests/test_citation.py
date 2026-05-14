from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.chat.citation import CitationError, enforce_citation
from backend.schema.models import (
    AgentRunLog,
    CitedValue,
    NormalizedRow,
    SourceType,
)


def test_cited_value_rejects_empty_source_row_ids() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CitedValue(
            value=100.0,
            currency="INR",
            metric_name="revenue",
            source_row_ids=[],
            source=SourceType.SHOPIFY,
        )
    assert "source_row_ids" in str(exc_info.value)


def test_citation_ref_format(sample_normalized_row: NormalizedRow) -> None:
    expected = "[shopify:shopify_order_99999]"
    assert sample_normalized_row.citation_ref() == expected


def test_agent_run_log_executed_always_false() -> None:
    with pytest.raises(ValidationError) as exc_info:
        AgentRunLog(
            agent_name="test_agent",
            merchant_id="550e8400-e29b-41d4-a716-446655440000",
            observation="test",
            reasoning="test",
            proposed_action="test",
            executed=True,
        )
    assert "executed" in str(exc_info.value)


def test_cited_value_accepts_valid_source_row_ids() -> None:
    cv = CitedValue(
        value=5000.0,
        currency="INR",
        metric_name="revenue",
        source_row_ids=["shopify_order_99999"],
        source=SourceType.SHOPIFY,
    )
    assert cv.source_row_ids == ["shopify_order_99999"]