from __future__ import annotations

import time

import structlog
import httpx
from fastapi import HTTPException, status

from backend.core.config import get_settings

logger = structlog.get_logger(__name__)

_RATE_LIMIT = 60
_WINDOW_SECONDS = 60

# In-memory fallback: {key: (count, window_start_monotonic)}
_in_memory: dict[str, tuple[int, float]] = {}


def _in_memory_check(merchant_id: str) -> int:
    """Single-process in-memory rate limiter used when Redis is not configured."""
    key = f"rate_limit:{merchant_id}"
    now = time.monotonic()
    count, window_start = _in_memory.get(key, (0, now))
    if now - window_start >= _WINDOW_SECONDS:
        count = 1
        window_start = now
    else:
        count += 1
    _in_memory[key] = (count, window_start)
    return count


async def check_rate_limit(merchant_id: str) -> None:
    settings = get_settings()
    log = logger.bind(merchant_id=merchant_id)

    if not settings.upstash_redis_url:
        count = _in_memory_check(merchant_id)
        log.debug("rate_limit_in_memory", count=count, limit=_RATE_LIMIT)
        if count > _RATE_LIMIT:
            log.warning("rate_limit_exceeded", backend="in_memory")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Max 60 requests per minute.",
                headers={"Retry-After": str(_WINDOW_SECONDS)},
            )
        return

    key = f"rate_limit:{merchant_id}"
    base_url = settings.upstash_redis_url

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            incr_response = await client.post(f"{base_url}/incr/{key}")
            incr_response.raise_for_status()
            count = incr_response.json().get("result", 1)

            if count == 1:
                await client.post(f"{base_url}/expire/{key}/{_WINDOW_SECONDS}")
    except Exception as exc:
        log.warning("rate_limit_redis_error", error=str(exc))
        # Fall back to in-memory so a Redis outage doesn't take down the API
        count = _in_memory_check(merchant_id)

    log = log.bind(count=count, limit=_RATE_LIMIT)

    if count > _RATE_LIMIT:
        log.warning("rate_limit_exceeded")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Max 60 requests per minute.",
            headers={"Retry-After": str(_WINDOW_SECONDS)},
        )

    log.info("rate_limit_checked")
