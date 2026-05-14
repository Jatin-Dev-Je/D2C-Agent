from __future__ import annotations

from typing import Any


METRIC_NAME_ENUM = [
    "revenue",
    "orders",
    "ad_spend",
    "roas",
    "impressions",
    "clicks",
    "cogs",
    "refunds",
    "avg_order_value",
    "shipping_cost",
    "rto",
]

GROUP_BY_ENUM = [
    "day",
    "week",
    "campaign",
    "product",
]


QUERY_METRICS_TOOL: dict[str, Any] = {
    "name": "query_metrics",
    "description": (
        "Retrieve normalized metric rows for a single merchant across a date range. "
        "Use this tool when the assistant needs citation-grounded raw metric rows."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "merchant_id": {
                "type": "string",
                "minLength": 1,
                "description": "Tenant identifier for the merchant whose metrics should be queried.",
            },
            "metric_name": {
                "type": "string",
                "enum": METRIC_NAME_ENUM,
                "description": "Normalized metric name to retrieve.",
            },
            "start_date": {
                "type": "string",
                "minLength": 1,
                "description": "Inclusive start date or datetime in ISO 8601 format.",
            },
            "end_date": {
                "type": "string",
                "minLength": 1,
                "description": "Inclusive end date or datetime in ISO 8601 format.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 1000,
                "description": "Maximum number of rows to return.",
            },
            "group_by": {
                "type": "string",
                "enum": GROUP_BY_ENUM,
                "description": "Optional grouping dimension for client-side shaping.",
            },
        },
        "required": ["merchant_id", "metric_name", "start_date", "end_date"],
    },
}

GET_METRIC_SUMMARY_TOOL: dict[str, Any] = {
    "name": "get_metric_summary",
    "description": (
        "Retrieve an aggregated metric total for a single merchant across a date range. "
        "Use this tool for grounded summary numbers."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "merchant_id": {
                "type": "string",
                "minLength": 1,
                "description": "Tenant identifier for the merchant whose metric should be summarized.",
            },
            "metric_name": {
                "type": "string",
                "enum": METRIC_NAME_ENUM,
                "description": "Normalized metric name to summarize.",
            },
            "start_date": {
                "type": "string",
                "minLength": 1,
                "description": "Inclusive start date or datetime in ISO 8601 format.",
            },
            "end_date": {
                "type": "string",
                "minLength": 1,
                "description": "Inclusive end date or datetime in ISO 8601 format.",
            },
        },
        "required": ["merchant_id", "metric_name", "start_date", "end_date"],
    },
}

COMPARE_METRIC_PERIODS_TOOL: dict[str, Any] = {
    "name": "compare_metric_periods",
    "description": (
        "Compare a metric between two date ranges for a single merchant. "
        "Use this tool for grounded period-over-period analysis."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "merchant_id": {
                "type": "string",
                "minLength": 1,
                "description": "Tenant identifier for the merchant whose metric should be compared.",
            },
            "metric_name": {
                "type": "string",
                "enum": METRIC_NAME_ENUM,
                "description": "Normalized metric name to compare.",
            },
            "current_start": {
                "type": "string",
                "minLength": 1,
                "description": "Inclusive start date or datetime for the current period.",
            },
            "current_end": {
                "type": "string",
                "minLength": 1,
                "description": "Inclusive end date or datetime for the current period.",
            },
            "previous_start": {
                "type": "string",
                "minLength": 1,
                "description": "Inclusive start date or datetime for the previous period.",
            },
            "previous_end": {
                "type": "string",
                "minLength": 1,
                "description": "Inclusive end date or datetime for the previous period.",
            },
        },
        "required": [
            "merchant_id",
            "metric_name",
            "current_start",
            "current_end",
            "previous_start",
            "previous_end",
        ],
    },
}

GET_CAMPAIGN_PERFORMANCE_TOOL: dict[str, Any] = {
    "name": "get_campaign_performance",
    "description": (
        "Retrieve campaign-level analytics for a single merchant over a date range. "
        "Use this tool for grounded Meta Ads campaign performance insights."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "merchant_id": {
                "type": "string",
                "minLength": 1,
                "description": "Tenant identifier for the merchant whose campaign analytics should be queried.",
            },
            "start_date": {
                "type": "string",
                "minLength": 1,
                "description": "Inclusive start date or datetime in ISO 8601 format.",
            },
            "end_date": {
                "type": "string",
                "minLength": 1,
                "description": "Inclusive end date or datetime in ISO 8601 format.",
            },
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 500,
                "description": "Maximum number of campaign rows to surface to the model.",
            },
        },
        "required": ["merchant_id", "start_date", "end_date"],
    },
}

GET_ROAS_SUMMARY_TOOL: dict[str, Any] = {
    "name": "get_roas_summary",
    "description": (
        "Retrieve grounded ROAS analytics for a single merchant across a date range. "
        "Use this tool for citation-safe revenue and ad spend summaries."
    ),
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "merchant_id": {
                "type": "string",
                "minLength": 1,
                "description": "Tenant identifier for the merchant whose ROAS should be summarized.",
            },
            "start_date": {
                "type": "string",
                "minLength": 1,
                "description": "Inclusive start date or datetime in ISO 8601 format.",
            },
            "end_date": {
                "type": "string",
                "minLength": 1,
                "description": "Inclusive end date or datetime in ISO 8601 format.",
            },
        },
        "required": ["merchant_id", "start_date", "end_date"],
    },
}

TOOLS_LIST: list[dict[str, Any]] = [
    QUERY_METRICS_TOOL,
    GET_METRIC_SUMMARY_TOOL,
    COMPARE_METRIC_PERIODS_TOOL,
    GET_CAMPAIGN_PERFORMANCE_TOOL,
    GET_ROAS_SUMMARY_TOOL,
]


def _to_gemini_schema(input_schema: dict[str, Any]) -> dict[str, Any]:
    """Convert Anthropic input_schema to Gemini parameters schema."""
    schema = dict(input_schema)
    schema.pop("additionalProperties", None)

    if "properties" in schema and isinstance(schema["properties"], dict):
        schema["properties"] = {
            key: {k: v for k, v in prop.items() if k != "additionalProperties"}
            for key, prop in schema["properties"].items()
        }

    return schema


GEMINI_TOOLS_LIST: list[dict[str, Any]] = [
    {
        "name": tool["name"],
        "description": tool["description"],
        "parameters": _to_gemini_schema(tool["input_schema"]),
    }
    for tool in TOOLS_LIST
]
