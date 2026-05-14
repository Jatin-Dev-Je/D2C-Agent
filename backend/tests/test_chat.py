from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.chat.citation import CitationValidationError, enforce_grounded_response
from backend.schema.models import CitedValue, SourceType
from backend.tests.conftest import make_test_token


# ── enforce_grounded_response ─────────────────────────────────────────────────

def test_enforce_grounded_response_passes_no_numbers() -> None:
    enforce_grounded_response(answer="Hello! I can help you.", cited_values=[])


def test_enforce_grounded_response_passes_with_citations(sample_cited_value: CitedValue) -> None:
    enforce_grounded_response(
        answer="Your revenue was ₹5,000.",
        cited_values=[sample_cited_value],
    )


def test_enforce_grounded_response_fails_numbers_no_citations() -> None:
    with pytest.raises(CitationValidationError, match="citations"):
        enforce_grounded_response(answer="Revenue was ₹50,000.", cited_values=[])


def test_enforce_grounded_response_fails_empty_answer(sample_cited_value: CitedValue) -> None:
    with pytest.raises(CitationValidationError):
        enforce_grounded_response(answer="   ", cited_values=[sample_cited_value])


# ── /chat/stream endpoint ─────────────────────────────────────────────────────

def _gemini_response(text: str) -> MagicMock:
    part = MagicMock()
    part.text = text
    part.function_call = None
    candidate = MagicMock()
    candidate.content.parts = [part]
    return MagicMock(candidates=[candidate])


@pytest.mark.asyncio
async def test_stream_returns_sse_events() -> None:
    from backend.services.llm_service import LLMService

    service = MagicMock(spec=LLMService)

    async def _fake_stream(*_args, **_kwargs):
        yield {"type": "token", "token": "Hello"}
        yield {"type": "citations", "citations": []}
        yield {"type": "confidence", "confidence": "low"}
        yield {"type": "done"}

    service.generate_grounded_response_stream = _fake_stream

    with patch("backend.chat.router.llm_service", service):
        from httpx import AsyncClient, ASGITransport
        from backend.main import app

        token = make_test_token()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/chat/stream",
                json={"query": "hello"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_stream_rejects_empty_query() -> None:
    from httpx import AsyncClient, ASGITransport
    from backend.main import app

    token = make_test_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/chat/stream",
            json={"query": "   "},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 422


def test_stream_rejects_missing_auth() -> None:
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app, raise_server_exceptions=False)
    response = client.post("/chat/stream", json={"query": "hello"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_query_endpoint_returns_json() -> None:
    from backend.services.llm_service import LLMService
    from backend.schema.models import ChatResponse

    service = MagicMock(spec=LLMService)
    service.generate_grounded_response = AsyncMock(return_value=ChatResponse(
        answer="Revenue was ₹5,000 [shopify:order_1]",
        cited_values=[CitedValue(
            value=5000,
            currency="INR",
            metric_name="revenue",
            source_row_ids=["order_1"],
            source=SourceType.SHOPIFY,
        )],
        confidence="high",
    ))

    with patch("backend.chat.router.llm_service", service):
        from httpx import AsyncClient, ASGITransport
        from backend.main import app

        token = make_test_token()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/chat/query",
                json={"query": "what is my revenue?"},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "citations" in data
        assert "confidence" in data
