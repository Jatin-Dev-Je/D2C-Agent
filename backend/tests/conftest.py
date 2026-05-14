from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.schema.models import (
    AgentRunLog,
    ChatResponse,
    CitedValue,
    MetricName,
    NormalizedRow,
    Provenance,
    SourceType,
)

SAMPLE_MERCHANT_ID = "550e8400-e29b-41d4-a716-446655440000"
SAMPLE_SOURCE_ROW_ID = "shopify_order_99999"
_JWT_SECRET = b"test-secret"


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def make_test_token(
    merchant_id: str = SAMPLE_MERCHANT_ID,
    email: str = "test@test.com",
    role: str = "merchant",
    exp_offset: int = 86400,
) -> str:
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64(json.dumps({
        "sub": merchant_id,
        "merchant_id": merchant_id,
        "email": email,
        "role": role,
        "exp": int(time.time()) + exp_offset,
    }).encode())
    sig = _b64(hmac.new(_JWT_SECRET, f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return f"{header}.{payload}.{sig}"


def make_expired_token() -> str:
    return make_test_token(exp_offset=-3600)


# ── Domain fixtures ───────────────────────────────────────────────────────────

@pytest.fixture
def sample_merchant_id() -> str:
    return SAMPLE_MERCHANT_ID


@pytest.fixture
def valid_token() -> str:
    return make_test_token()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {make_test_token()}"}


@pytest.fixture
def sample_provenance() -> Provenance:
    return Provenance(
        source=SourceType.SHOPIFY,
        source_row_id=SAMPLE_SOURCE_ROW_ID,
        source_url="https://test.myshopify.com/admin/orders/99999",
    )


@pytest.fixture
def sample_normalized_row(sample_provenance: Provenance) -> NormalizedRow:
    return NormalizedRow(
        merchant_id=SAMPLE_MERCHANT_ID,
        metric_name=MetricName.REVENUE,
        value=5000.0,
        currency="INR",
        occurred_at=datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc),
        provenance=sample_provenance,
    )


@pytest.fixture
def sample_cited_value() -> CitedValue:
    return CitedValue(
        value=5000.0,
        currency="INR",
        metric_name="revenue",
        source_row_ids=[SAMPLE_SOURCE_ROW_ID],
        source=SourceType.SHOPIFY,
    )


@pytest.fixture
def sample_chat_response(sample_cited_value: CitedValue) -> ChatResponse:
    return ChatResponse(
        answer=f"Your revenue was ₹5,000 [shopify:{SAMPLE_SOURCE_ROW_ID}]",
        cited_values=[sample_cited_value],
        confidence="high",
        suggested_followups=["What was my ad spend?", "How does this compare last week?"],
    )


# ── Infrastructure mocks ──────────────────────────────────────────────────────

@pytest.fixture
def mock_supabase() -> MagicMock:
    mock = MagicMock()
    mock.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])
    mock.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[])
    mock.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value = MagicMock(data=[])
    mock.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute.return_value = MagicMock(data=[])
    return mock


@pytest.fixture
def mock_gemini() -> MagicMock:
    mock = MagicMock()
    part = MagicMock()
    part.text = "Mocked Gemini answer"
    part.function_call = None
    candidate = MagicMock()
    candidate.content.parts = [part]
    mock.models.generate_content.return_value = MagicMock(candidates=[candidate])
    return mock


# ── App client ────────────────────────────────────────────────────────────────

@pytest.fixture
def app_client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient with Supabase and Gemini mocked out."""
    import backend.core.database as db_module

    monkeypatch.setattr(db_module, "get_db", lambda: MagicMock(
        table=MagicMock(return_value=MagicMock(
            select=MagicMock(return_value=MagicMock(
                eq=MagicMock(return_value=MagicMock(
                    limit=MagicMock(return_value=MagicMock(execute=MagicMock(return_value=MagicMock(data=[]))))
                ))
            ))
        ))
    ))

    from backend.main import app
    return TestClient(app, raise_server_exceptions=False)
