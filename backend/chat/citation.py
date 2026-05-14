from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from backend.core.logging import get_logger
from backend.schema.models import CitationTrace, CitedValue, NormalizedRow


NUMERIC_REGEX = re.compile(r"(?:₹|\$)?\d[\d,]*(?:\.\d+)?%?")


class CitationValidationError(Exception):
    """Raised when grounded AI citation validation fails."""


CitationError = CitationValidationError


logger = get_logger(__name__)


def extract_numeric_tokens(text: str) -> list[str]:
    """
    Extract numeric tokens from AI response text.

    Supports:
    - currency values
    - percentages
    - decimal values
    - comma-separated numbers
    """

    if not text.strip():
        return []

    return NUMERIC_REGEX.findall(text)


def _validate_row_id(row_id: str) -> str:
    """Validate a cited source row identifier."""

    cleaned = row_id.strip()
    if not cleaned:
        raise CitationValidationError("Blank source_row_id detected")

    return cleaned


def _validate_decimal_value(value: Decimal | str | int | float) -> Decimal:
    """Validate that a value is safely representable as Decimal."""

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise CitationValidationError("Invalid decimal value detected") from exc


def validate_cited_values(
    cited_values: list[CitedValue],
) -> None:
    """
    Validate grounded cited values.

    Rejects empty citations, blank source row IDs, and invalid decimal values.
    """

    if not cited_values:
        raise CitationValidationError("At least one cited value is required")

    for cited_value in cited_values:
        if not cited_value.source_row_ids:
            raise CitationValidationError("source_row_ids cannot be empty")

        for row_id in cited_value.source_row_ids:
            _validate_row_id(row_id)

        _validate_decimal_value(cited_value.value)


def build_citation_trace(
    rows: list[NormalizedRow],
    metric_name: str,
    operation: str,
) -> CitationTrace:
    """
    Build deterministic aggregation lineage for grounded responses.
    """

    source_row_ids = sorted(
        {
            row.provenance.source_row_id
            for row in rows
            if row.provenance and row.provenance.source_row_id.strip()
        }
    )

    return CitationTrace(
        metric_name=metric_name,
        operation=operation,
        source_row_ids=source_row_ids,
    )


def format_inline_citations(
    cited_values: list[CitedValue],
) -> str:
    """
    Format compact inline citation references.

    Example:
    [shopify:row_1], [meta_ads:row_2]
    """

    formatted: list[str] = []

    for cited_value in cited_values:
        for row_id in cited_value.source_row_ids:
            cleaned_row_id = _validate_row_id(row_id)
            formatted.append(f"[{cited_value.source.value}:{cleaned_row_id}]")

    return ", ".join(sorted(set(formatted)))


def enforce_citation(
    answer: str,
    cited_values: list[CitedValue],
) -> None:
    """Alias for enforce_grounded_response — backward-compatible name."""
    enforce_grounded_response(answer=answer, cited_values=cited_values)


def enforce_grounded_response(
    answer: str,
    cited_values: list[CitedValue],
) -> None:
    """
    Enforce grounded AI response constraints.

    Rejects empty AI answers, uncited numeric claims, and invalid citation data.
    """

    cleaned_answer = answer.strip()
    if not cleaned_answer:
        raise CitationValidationError("AI answer cannot be empty")

    numeric_tokens = extract_numeric_tokens(cleaned_answer)
    if numeric_tokens and not cited_values:
        raise CitationValidationError("Numerical claims require citations")

    if cited_values:
        validate_cited_values(cited_values)

    logger.info(
        "grounded_response_validated",
        numeric_tokens=len(numeric_tokens),
        citations=len(cited_values),
    )