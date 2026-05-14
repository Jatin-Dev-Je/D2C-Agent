from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.agents.ad_watchdog import AdWatchdogAgent
from backend.core.database import get_agent_logs, save_agent_log
from backend.middleware.auth import get_merchant_id
from backend.middleware.rate_limit import check_rate_limit
from backend.repositories.metrics_repository import MetricsRepository
from backend.services.metrics_service import MetricsService


router = APIRouter(prefix="/agents", tags=["agents"])
logger = structlog.get_logger(__name__)


@router.get("/logs")
async def list_agent_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    merchant_id: str = Depends(get_merchant_id),
) -> dict[str, Any]:
    """Return paginated agent run logs for the authenticated merchant."""

    await check_rate_limit(merchant_id)
    logs = await get_agent_logs(
        merchant_id=merchant_id,
        limit=limit,
        offset=offset,
    )
    return {
        "merchant_id": merchant_id,
        "logs": logs,
        "count": len(logs),
        "limit": limit,
        "offset": offset,
    }


@router.post("/trigger", status_code=status.HTTP_201_CREATED)
async def trigger_agent(
    merchant_id: str = Depends(get_merchant_id),
) -> dict[str, Any]:
    """Manually trigger an ad watchdog run for the authenticated merchant."""

    await check_rate_limit(merchant_id)
    log = logger.bind(merchant_id=merchant_id, route="/agents/trigger")
    log.info("agent_trigger_requested")

    agent = AdWatchdogAgent(
        metrics_service=MetricsService(repository=MetricsRepository())
    )

    try:
        result = await agent.execute(merchant_id)
        agent_log = agent.build_agent_log(merchant_id=merchant_id, result=result)
        await save_agent_log(agent_log)

        log.info(
            "agent_trigger_completed",
            recommendations=len(result.recommendations),
            citations=len(agent_log.citations),
            status=agent_log.status,
            duration_ms=result.execution_duration_ms,
        )

        return {
            "id": agent_log.id,
            "agent_name": agent_log.agent_name,
            "merchant_id": agent_log.merchant_id,
            "triggered_at": agent_log.triggered_at.isoformat(),
            "observation": agent_log.observation,
            "reasoning": agent_log.reasoning,
            "proposed_action": agent_log.proposed_action,
            "estimated_saving_inr": str(agent_log.estimated_saving_inr) if agent_log.estimated_saving_inr is not None else None,
            "citations": agent_log.citations,
            "executed": agent_log.executed,
            "status": agent_log.status,
            "execution_duration_ms": result.execution_duration_ms,
            "findings": result.metadata.get("findings", []),
        }

    except Exception as exc:
        log.exception("agent_trigger_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Agent execution failed",
        ) from None
