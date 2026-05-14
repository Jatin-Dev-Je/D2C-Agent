from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import Any

import structlog
from supabase import Client, create_client

from backend.core.config import get_settings
from backend.schema.models import AgentRunLog, NormalizedRow


logger = structlog.get_logger(__name__)


@lru_cache(maxsize=1)
def get_db() -> Client:
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_key)


def _serialize_row(row: NormalizedRow, merchant_id: str) -> dict[str, Any]:
    return {
        "merchant_id": merchant_id,
        "source": row.provenance.source.value,
        "source_row_id": row.provenance.source_row_id,
        "metric_name": row.metric_name.value,
        "value": str(row.value),
        "currency": row.currency,
        "dimensions": row.dimensions,
        "occurred_at": row.occurred_at.isoformat(),
        "synced_at": row.provenance.synced_at.isoformat(),
        "raw_payload": row.provenance.raw_payload,
    }


def _serialize_agent_log(run_log: AgentRunLog) -> dict[str, Any]:
    return {
        "id": run_log.id,
        "agent_name": run_log.agent_name,
        "merchant_id": run_log.merchant_id,
        "triggered_at": run_log.triggered_at.isoformat(),
        "observation": run_log.observation,
        "reasoning": run_log.reasoning,
        "proposed_action": run_log.proposed_action,
        "estimated_saving": str(run_log.estimated_saving_inr) if run_log.estimated_saving_inr is not None else None,
        "citations": run_log.citations,
        "executed": run_log.executed,
        "status": run_log.status,
    }


async def upsert_rows(rows: list[NormalizedRow], merchant_id: str) -> int:
    log = logger.bind(merchant_id=merchant_id)

    if not rows:
        log.info("upsert_skipped", reason="empty_rows")
        return 0

    payload = [_serialize_row(row=row, merchant_id=merchant_id) for row in rows]
    log.info("upserting_metric_rows", rows_attempted=len(payload))

    db = get_db()
    response = await asyncio.to_thread(
        lambda: db.table("metric_events")
        .upsert(payload, on_conflict="merchant_id,source,source_row_id", ignore_duplicates=True)
        .execute()
    )

    inserted_count = len(response.data) if response.data else 0
    log.info(
        "upsert_metric_rows_complete",
        rows_attempted=len(payload),
        rows_inserted=inserted_count,
    )
    return inserted_count


async def save_agent_log(run_log: AgentRunLog) -> None:
    log = logger.bind(
        merchant_id=run_log.merchant_id,
        agent_name=run_log.agent_name,
    )
    payload = _serialize_agent_log(run_log)
    db = get_db()

    await asyncio.to_thread(
        lambda: db.table("agent_run_logs").insert(payload).execute()
    )
    log.info("agent_log_saved", status=run_log.status)


async def get_agent_logs(
    merchant_id: str,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return agent run logs for a merchant, newest first."""

    db = get_db()
    response = await asyncio.to_thread(
        lambda: db.table("agent_run_logs")
        .select("*")
        .eq("merchant_id", merchant_id)
        .order("triggered_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return response.data or []


async def get_distinct_merchant_ids() -> list[str]:
    """Return all registered merchant IDs from the merchants table."""
    db = get_db()
    response = await asyncio.to_thread(
        lambda: db.table("merchants").select("merchant_id").execute()
    )
    return [row["merchant_id"] for row in (response.data or []) if row.get("merchant_id")]


async def register_merchant(merchant_id: str, email: str, role: str = "merchant") -> dict[str, Any]:
    """Upsert a merchant record. Safe to call on every login."""
    db = get_db()
    payload = {
        "merchant_id": merchant_id.strip(),
        "email": email.strip(),
        "role": role.strip() or "merchant",
    }
    response = await asyncio.to_thread(
        lambda: db.table("merchants")
        .upsert(payload, on_conflict="merchant_id")
        .execute()
    )
    row = (response.data or [{}])[0]
    logger.info("merchant_registered", merchant_id=merchant_id)
    return row


async def get_merchant(merchant_id: str) -> dict[str, Any] | None:
    """Return a single merchant record or None if not found."""
    db = get_db()
    response = await asyncio.to_thread(
        lambda: db.table("merchants")
        .select("*")
        .eq("merchant_id", merchant_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None
