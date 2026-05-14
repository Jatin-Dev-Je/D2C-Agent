from __future__ import annotations

import json
from time import perf_counter
from typing import Literal
from uuid import uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

from backend.chat.citation import CitationValidationError
from backend.core.logging import bind_merchant_id, bind_request_id, clear_runtime_context
from backend.middleware.auth import get_merchant_id
from backend.middleware.rate_limit import check_rate_limit
from backend.schema.models import CitedValue
from backend.services.llm_service import LLMService


router = APIRouter(
    prefix="/chat",
    tags=["chat"],
)

logger = structlog.get_logger(__name__)
llm_service = LLMService()


class ChatRequest(BaseModel):
    """Validated request payload for grounded chat operations."""

    query: str = Field(..., min_length=1, max_length=4000)

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        """Reject blank or whitespace-only prompts."""

        cleaned = value.strip()
        if not cleaned:
            raise ValueError("query cannot be empty")

        return cleaned


class ChatAPIResponse(BaseModel):
    """Structured API response for grounded chat answers."""

    answer: str
    citations: list[str]
    confidence: Literal["high", "medium", "low"]


def format_sse_event(data: dict[str, object]) -> str:
    """Serialize an SSE payload as a single event frame."""

    return f"data: {json.dumps(data, default=str, ensure_ascii=False)}\n\n"


def _citation_summaries(citations: list[CitedValue]) -> list[str]:
    """Convert cited values into compact citation summaries."""

    return [citation.citation_summary() for citation in citations]


def _safe_chat_error_message(error: Exception) -> str:
    """Map internal exceptions to a stable client-facing message."""

    if isinstance(error, CitationValidationError):
        return "Unable to produce a grounded answer for that request."

    return "Internal server error"


async def stream_response_generator(
    merchant_id: str,
    query: str,
):
    """Stream grounded chat events using Anthropic token streaming."""

    try:
        async for event in llm_service.generate_grounded_response_stream(
            merchant_id=merchant_id,
            user_query=query,
        ):
            yield format_sse_event(event)

    except Exception as error:
        logger.warning(
            "chat_stream_failed",
            merchant_id=merchant_id,
            error=str(error),
        )
        yield format_sse_event(
            {
                "type": "error",
                "message": _safe_chat_error_message(error),
            }
        )
        yield format_sse_event({"type": "done"})


@router.post("/query", response_model=ChatAPIResponse)
async def chat_query(
    request: ChatRequest,
    merchant_id: str = Depends(get_merchant_id),
) -> ChatAPIResponse:
    """Generate a grounded chat answer for a single merchant."""

    await check_rate_limit(merchant_id)
    request_id = str(uuid4())
    started_at = perf_counter()
    request_logger = logger.bind(
        request_id=request_id,
        merchant_id=merchant_id,
        route="/chat/query",
    )

    bind_request_id(request_id)
    bind_merchant_id(merchant_id)

    request_logger.info(
        "chat_request_received",
        query_length=len(request.query),
    )

    try:
        response = await llm_service.generate_grounded_response(
            merchant_id=merchant_id,
            user_query=request.query,
        )

        response_payload = ChatAPIResponse(
            answer=response.answer,
            citations=_citation_summaries(response.cited_values),
            confidence=response.confidence,
        )

        request_logger.info(
            "chat_request_completed",
            response_time_ms=round((perf_counter() - started_at) * 1000, 2),
            citations=len(response_payload.citations),
            confidence=response_payload.confidence,
        )

        return response_payload

    except CitationValidationError:
        request_logger.warning(
            "chat_request_grounding_failed",
            response_time_ms=round((perf_counter() - started_at) * 1000, 2),
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unable to produce a grounded answer for that request.",
        ) from None

    except Exception:
        request_logger.exception(
            "chat_request_failed",
            response_time_ms=round((perf_counter() - started_at) * 1000, 2),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from None

    finally:
        clear_runtime_context()


@router.post("/stream")
async def stream_chat(
    request: ChatRequest,
    merchant_id: str = Depends(get_merchant_id),
) -> StreamingResponse:
    """Stream a grounded chat response as SSE events."""

    await check_rate_limit(merchant_id)
    request_id = str(uuid4())
    started_at = perf_counter()
    request_logger = logger.bind(
        request_id=request_id,
        merchant_id=merchant_id,
        route="/chat/stream",
    )

    bind_request_id(request_id)
    bind_merchant_id(merchant_id)

    request_logger.info(
        "chat_stream_received",
        query_length=len(request.query),
    )

    async def event_generator():
        try:
            async for event_frame in stream_response_generator(
                merchant_id=merchant_id,
                query=request.query,
            ):
                yield event_frame

            request_logger.info(
                "chat_stream_completed",
                response_time_ms=round((perf_counter() - started_at) * 1000, 2),
            )

        except Exception:
            request_logger.exception(
                "chat_stream_failed",
                response_time_ms=round((perf_counter() - started_at) * 1000, 2),
            )
            yield format_sse_event(
                {
                    "type": "error",
                    "message": "Internal server error",
                }
            )
            yield format_sse_event({"type": "done"})

        finally:
            clear_runtime_context()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )