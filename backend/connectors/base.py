from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import structlog

from backend.schema.models import (
    ConnectorSyncResult,
    DateRange,
    NormalizedRow,
    Provenance,
)


logger = structlog.get_logger(__name__)


def _ensure_timezone_aware(value: datetime, field_name: str) -> datetime:
    """Validate that a datetime is timezone-aware and normalize it to UTC."""

    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")

    return value.astimezone(timezone.utc)


class BaseConnector(ABC):
    """
    Shared abstraction for all external ingestion connectors.

    Connectors are responsible only for:
    - calling external systems
    - normalizing rows into NormalizedRow objects
    - guaranteeing provenance on every row
    - validating health of upstream systems

    Persistence, analytics, and AI orchestration belong elsewhere.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return a human-readable connector name for logs and telemetry."""

    @abstractmethod
    async def fetch(
        self,
        merchant_id: str,
        date_range: DateRange,
    ) -> list[NormalizedRow]:
        """
        Pull external data and normalize it into provenance-safe rows.

        Every returned row must contain valid provenance and timezone-aware
        datetimes.
        """

    @abstractmethod
    async def health_check(self, merchant_id: str) -> bool:
        """
        Validate credentials and upstream reachability.

        The method must never raise and should return False on failure.
        """

    def get_logger(self, merchant_id: str) -> structlog.stdlib.BoundLogger:
        """
        Return a connector-bound structured logger.

        Merchant and connector name are always bound for operational tracing.
        """

        return logger.bind(merchant_id=merchant_id, connector_name=self.source_name)

    def validate_rows(self, rows: list[NormalizedRow]) -> list[NormalizedRow]:
        """
        Validate normalized rows before they leave the connector boundary.

        Enforces:
        - provenance presence
        - timezone-aware timestamps
        - non-empty merchant IDs
        - non-empty source row identifiers
        - stable UTC normalization
        """

        validated_rows: list[NormalizedRow] = []

        for index, row in enumerate(rows):
            if not isinstance(row, NormalizedRow):
                raise TypeError(f"rows[{index}] must be a NormalizedRow instance")

            if not isinstance(row.provenance, Provenance):
                raise ValueError(f"rows[{index}].provenance must be present")

            if not row.merchant_id.strip():
                raise ValueError(f"rows[{index}].merchant_id cannot be empty")

            if not row.provenance.source_row_id.strip():
                raise ValueError(f"rows[{index}].provenance.source_row_id cannot be empty")

            normalized_occurred_at = _ensure_timezone_aware(
                row.occurred_at,
                f"rows[{index}].occurred_at",
            )
            normalized_synced_at = _ensure_timezone_aware(
                row.provenance.synced_at,
                f"rows[{index}].provenance.synced_at",
            )

            if normalized_occurred_at != row.occurred_at or normalized_synced_at != row.provenance.synced_at:
                validated_rows.append(
                    row.model_copy(
                        update={
                            "occurred_at": normalized_occurred_at,
                            "provenance": row.provenance.model_copy(
                                update={"synced_at": normalized_synced_at}
                            ),
                        }
                    )
                )
                continue

            validated_rows.append(row)

        return validated_rows

    def build_sync_result(
        self,
        merchant_id: str,
        rows_fetched: int,
        rows_inserted: int,
        failed_rows: int,
        started_at: datetime,
        completed_at: datetime,
        success: bool,
    ) -> ConnectorSyncResult:
        """
        Build standardized connector sync metadata for observability.

        This keeps downstream sync logging and analytics consistent across
        connectors and future runtime backends.
        """

        normalized_started_at = _ensure_timezone_aware(started_at, "started_at")
        normalized_completed_at = _ensure_timezone_aware(completed_at, "completed_at")

        if normalized_started_at > normalized_completed_at:
            raise ValueError("started_at cannot be after completed_at")

        duration_ms = int(
            (normalized_completed_at - normalized_started_at).total_seconds() * 1000
        )

        return ConnectorSyncResult(
            connector_name=self.source_name,
            merchant_id=merchant_id,
            rows_fetched=rows_fetched,
            rows_inserted=rows_inserted,
            failed_rows=failed_rows,
            duration_ms=duration_ms,
            started_at=normalized_started_at,
            completed_at=normalized_completed_at,
            success=success,
        )