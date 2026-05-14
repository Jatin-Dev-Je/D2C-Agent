from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


DECIMAL_PRECISION = Decimal("0.01")


def normalize_decimal(value: Decimal | str | int | float) -> Decimal:
    """
    Normalize monetary/business metric precision.

    Prevents floating point drift across:
    - ROAS calculations
    - revenue aggregation
    - AI cited values
    - analytics workloads
    """

    decimal_value = Decimal(str(value))
    return decimal_value.quantize(
        DECIMAL_PRECISION,
        rounding=ROUND_HALF_UP,
    )


class SourceType(str, Enum):
    SHOPIFY = "shopify"
    META_ADS = "meta_ads"
    SHIPROCKET = "shiprocket"


class MetricName(str, Enum):
    REVENUE = "revenue"
    ORDERS = "orders"
    AD_SPEND = "ad_spend"
    ROAS = "roas"
    IMPRESSIONS = "impressions"
    CLICKS = "clicks"
    COGS = "cogs"
    REFUNDS = "refunds"
    AVG_ORDER_VALUE = "avg_order_value"
    SHIPPING_COST = "shipping_cost"
    RTO = "rto"


@dataclass(slots=True)
class DateRange:
    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None:
            raise ValueError("DateRange.start must be timezone-aware")

        if self.end.tzinfo is None:
            raise ValueError("DateRange.end must be timezone-aware")

        if self.start > self.end:
            raise ValueError("DateRange.start cannot be after end")


class Provenance(BaseModel):
    """
    Tracks exact source lineage for grounded AI responses.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    source: SourceType = Field(
        ...,
        description="Origin connector/source system",
        examples=["shopify"],
    )

    source_row_id: str = Field(
        ...,
        min_length=1,
        description="Unique source record identifier",
        examples=["shopify_order_12345"],
    )

    source_url: str | None = Field(
        default=None,
        description="Optional deep-link to source object",
    )

    synced_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    raw_payload: dict[str, Any] | None = Field(
        default=None,
        description="Raw upstream payload for debugging/replay",
    )

    @field_validator("synced_at")
    @classmethod
    def validate_synced_at(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            raise ValueError("synced_at must be timezone-aware")

        return value.astimezone(timezone.utc)

    @field_validator("source_row_id")
    @classmethod
    def validate_source_row_id(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("source_row_id cannot be empty")

        return cleaned

    def summary(self) -> str:
        return f"{self.source.value}:{self.source_row_id}"


class NormalizedRow(BaseModel):
    """
    Canonical normalized metric row used across all connectors.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    id: str = Field(
        default_factory=lambda: str(uuid4()),
    )

    merchant_id: str = Field(
        ...,
        min_length=1,
    )

    metric_name: MetricName

    value: Decimal = Field(
        ...,
        description="Normalized business metric value",
    )

    currency: str = Field(
        default="INR",
    )

    dimensions: dict[str, str] = Field(
        default_factory=dict,
    )

    occurred_at: datetime

    provenance: Provenance

    @field_validator("value")
    @classmethod
    def validate_value(
        cls,
        value: Decimal,
    ) -> Decimal:
        return normalize_decimal(value)

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must be timezone-aware")

        return value.astimezone(timezone.utc)

    @field_validator("merchant_id")
    @classmethod
    def validate_merchant_id(
        cls,
        value: str,
    ) -> str:
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("merchant_id cannot be empty")

        return cleaned

    def citation_ref(self) -> str:
        return (
            f"[{self.provenance.source.value}:"
            f"{self.provenance.source_row_id}]"
        )

    def db_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "merchant_id": self.merchant_id,
            "source": self.provenance.source.value,
            "source_row_id": self.provenance.source_row_id,
            "metric_name": self.metric_name.value,
            "value": str(self.value),
            "currency": self.currency,
            "dimensions": self.dimensions,
            "occurred_at": self.occurred_at.isoformat(),
            "synced_at": self.provenance.synced_at.isoformat(),
            "raw_payload": self.provenance.raw_payload,
        }


class CitedValue(BaseModel):
    """
    AI-grounded numerical value with provenance guarantees.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    value: Decimal

    currency: str

    metric_name: str

    source_row_ids: list[str]

    source: SourceType

    @field_validator("value")
    @classmethod
    def validate_value(
        cls,
        value: Decimal,
    ) -> Decimal:
        return normalize_decimal(value)

    @field_validator("source_row_ids")
    @classmethod
    def validate_source_row_ids(
        cls,
        value: list[str],
    ) -> list[str]:
        if not value:
            raise ValueError(
                "source_row_ids cannot be empty"
            )

        cleaned = [row_id.strip() for row_id in value if row_id.strip()]

        if not cleaned:
            raise ValueError(
                "source_row_ids cannot be blank"
            )

        return cleaned

    def citation_summary(self) -> str:
        return ", ".join(self.source_row_ids)


class CitationTrace(BaseModel):
    """
    Tracks how a cited numerical answer was derived.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    metric_name: str

    operation: str

    source_row_ids: list[str]

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class ChatResponse(BaseModel):
    """
    Structured AI response with grounded citations.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    answer: str

    cited_values: list[CitedValue]

    confidence: Literal[
        "high",
        "medium",
        "low",
    ] = "high"

    suggested_followups: list[str] = Field(
        default_factory=list,
    )


class AgentRunLog(BaseModel):
    """
    Immutable autonomous agent decision log.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    id: str = Field(
        default_factory=lambda: str(uuid4()),
    )

    agent_name: str

    merchant_id: str

    triggered_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    observation: str

    reasoning: str

    proposed_action: str

    estimated_saving_inr: Decimal | None = None

    citations: list[str] = Field(
        default_factory=list,
    )

    executed: bool = False

    status: str = "proposed"

    @field_validator("estimated_saving_inr")
    @classmethod
    def validate_estimated_saving(
        cls,
        value: Decimal | None,
    ) -> Decimal | None:
        if value is None:
            return None

        return normalize_decimal(value)

    @model_validator(mode="after")
    def validate_executed(self) -> "AgentRunLog":
        if self.executed:
            raise ValueError(
                "AgentRunLog.executed must always remain False"
            )

        return self


class ConnectorSyncResult(BaseModel):
    """
    Operational metadata for connector sync runs.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    connector_name: str

    merchant_id: str

    rows_fetched: int = 0

    rows_inserted: int = 0

    failed_rows: int = 0

    duration_ms: int

    started_at: datetime

    completed_at: datetime

    success: bool = True