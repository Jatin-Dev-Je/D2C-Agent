from __future__ import annotations

import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import structlog
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.core.logging import get_logger
from backend.schema.models import AgentRunLog, CitedValue


class AgentExecutionResult(BaseModel):
    """Structured outcome for a deterministic recommendation-only agent run."""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    success: bool
    observations: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    cited_values: list[CitedValue] = Field(default_factory=list)
    execution_duration_ms: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    estimated_saving_inr: Any = None

    @field_validator("observations", "recommendations")
    @classmethod
    def validate_text_items(cls, value: list[str]) -> list[str]:
        """Remove blank items while preserving order."""

        return [item.strip() for item in value if item and item.strip()]

    @field_validator("execution_duration_ms")
    @classmethod
    def validate_duration(cls, value: int) -> int:
        """Reject negative execution durations."""

        if value < 0:
            raise ValueError("execution_duration_ms cannot be negative")

        return value

    @model_validator(mode="after")
    def validate_content(self) -> "AgentExecutionResult":
        """Ensure successful runs always carry at least one recommendation."""

        if self.success and not self.recommendations:
            raise ValueError(
                "successful agent runs must include at least one recommendation"
            )

        return self


class BaseAgent(ABC):
    """Deterministic recommendation-only agent abstraction."""

    @property
    @abstractmethod
    def agent_name(self) -> str:
        """Return the unique stable name for this agent."""

    @abstractmethod
    async def run(self, merchant_id: str) -> AgentExecutionResult:
        """Run deterministic analysis and return recommendations only."""

    def get_logger(self, merchant_id: str) -> structlog.stdlib.BoundLogger:
        """Return a bound structured logger for the current agent execution."""

        return get_logger(__name__).bind(
            merchant_id=merchant_id,
            agent_name=self.agent_name,
        )

    def build_agent_log(
        self,
        merchant_id: str,
        result: AgentExecutionResult,
    ) -> AgentRunLog:
        """Convert an execution result into an immutable audit log entry."""

        cited_row_ids: list[str] = []
        for cited_value in result.cited_values:
            cited_row_ids.extend(cited_value.source_row_ids)

        unique_cited_row_ids = sorted(set(cited_row_ids))
        observation_text = (
            "\n".join(result.observations)
            if result.observations
            else "No observations recorded."
        )
        recommendation_text = (
            "\n".join(result.recommendations)
            if result.recommendations
            else "No recommendation proposed."
        )

        metadata_parts = [
            f"{key}={value}"
            for key, value in sorted(result.metadata.items(), key=lambda item: item[0])
        ]
        reasoning_parts = [
            f"Observations:\n{observation_text}",
            f"Recommendations:\n{recommendation_text}",
        ]
        if metadata_parts:
            metadata_text = "\n".join(metadata_parts)
            reasoning_parts.append(f"Metadata:\n{metadata_text}")

        from decimal import Decimal
        estimated_saving: Decimal | None = None
        if result.estimated_saving_inr is not None:
            try:
                estimated_saving = Decimal(str(result.estimated_saving_inr))
            except Exception:
                pass

        return AgentRunLog(
            agent_name=self.agent_name,
            merchant_id=merchant_id,
            observation=observation_text,
            reasoning="\n\n".join(reasoning_parts),
            proposed_action=(
                result.recommendations[0]
                if result.recommendations
                else "No recommendation proposed."
            ),
            estimated_saving_inr=estimated_saving,
            citations=unique_cited_row_ids,
            executed=False,
            status="proposed" if result.success else "failed",
        )

    async def _safe_execute(self, merchant_id: str) -> AgentExecutionResult:
        """Run the agent and convert unexpected failures into structured results."""

        log = self.get_logger(merchant_id)

        try:
            return await self.run(merchant_id=merchant_id)
        except Exception as exc:
            log.exception(
                "agent_execution_failed",
                error_type=exc.__class__.__name__,
                error=str(exc),
            )
            return AgentExecutionResult(
                success=False,
                observations=[
                    "Agent execution failed before producing a recommendation."
                ],
                recommendations=[
                    "Review agent logs and input data before retrying."
                ],
                cited_values=[],
                execution_duration_ms=0,
                metadata={
                    "error_type": exc.__class__.__name__,
                    "error": str(exc),
                },
            )

    async def execute(self, merchant_id: str) -> AgentExecutionResult:
        """Execute the agent lifecycle with standardized observability and timing."""

        log = self.get_logger(merchant_id)
        started_at = time.perf_counter()
        started_at_utc = datetime.now(timezone.utc)

        log.info("agent_execution_started")

        result = await self._safe_execute(merchant_id=merchant_id)

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        completed_at_utc = datetime.now(timezone.utc)

        result.execution_duration_ms = duration_ms
        result.metadata = {
            **result.metadata,
            "started_at_utc": started_at_utc.isoformat(),
            "completed_at_utc": completed_at_utc.isoformat(),
        }

        log.info(
            "agent_execution_completed",
            success=result.success,
            duration_ms=duration_ms,
            observations=len(result.observations),
            recommendations=len(result.recommendations),
            cited_values=len(result.cited_values),
        )

        return result