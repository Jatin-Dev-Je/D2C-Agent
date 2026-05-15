from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, AsyncIterator, Literal

from google import genai
from google.genai import types

try:
    from langfuse import Langfuse as _LangfuseClient
    _LANGFUSE_AVAILABLE = True
except ImportError:
    _LANGFUSE_AVAILABLE = False

from backend.chat.citation import (
    CitationValidationError,
    build_citation_trace,
    enforce_grounded_response,
    validate_cited_values,
)
from backend.services.tools import GEMINI_TOOLS_LIST
from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.repositories.metrics_repository import MetricsRepository
from backend.schema.models import ChatResponse, CitedValue, MetricName, NormalizedRow, Provenance, SourceType
from backend.services.metrics_service import MetricsService


def _normalize_decimal(value: Decimal | str | int | float) -> Decimal:
    return Decimal(str(value))


def _ensure_timezone_aware(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_iso_datetime(value: Any, field_name: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise CitationValidationError(f"{field_name} must be a non-empty ISO datetime string")
    cleaned = value.strip().replace("Z", "+00:00")
    # Handle plain date strings like "2026-05-08" — assume start of day UTC
    if len(cleaned) == 10:
        cleaned = f"{cleaned}T00:00:00+00:00"
    parsed = datetime.fromisoformat(cleaned)
    return _ensure_timezone_aware(parsed, field_name)


class LLMService:
    """
    Deterministic LLM orchestration runtime using Google Gemini (google-genai SDK).

    Owns tool dispatch, citation enforcement, and model interaction.
    Does not own business logic, persistence, or analytics calculations.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.logger = get_logger(__name__)
        self.metrics_service = MetricsService(repository=MetricsRepository())
        self.model_name = self.settings.llm_model
        self.max_tool_iterations = self.settings.max_tool_iterations
        self.request_timeout_seconds = self.settings.llm_timeout_seconds
        self.client = genai.Client(api_key=self.settings.gemini_api_key)
        self._langfuse = self._init_langfuse()

        if self.max_tool_iterations < 1:
            raise ValueError("max_tool_iterations must be at least 1")

    def _init_langfuse(self) -> Any:
        if not _LANGFUSE_AVAILABLE:
            return None
        s = self.settings
        if s.langfuse_public_key and s.langfuse_secret_key:
            return _LangfuseClient(
                public_key=s.langfuse_public_key,
                secret_key=s.langfuse_secret_key,
                host=s.langfuse_host,
            )
        return None

    def _lf_trace(self, merchant_id: str, query: str) -> Any:
        if not self._langfuse:
            return None
        return self._langfuse.trace(
            name="d2c_chat",
            user_id=merchant_id,
            input={"query": query},
            metadata={"model": self.model_name},
        )

    def _lf_generation(self, trace: Any, iteration: int, input_text: str, output_text: str) -> None:
        if not trace:
            return
        trace.generation(
            name=f"gemini_{iteration}",
            model=self.model_name,
            input=input_text[:2000],
            output=output_text[:2000],
        )

    def _lf_finish(self, trace: Any, answer: str, citations: int, confidence: str) -> None:
        if not trace:
            return
        trace.update(
            output={"answer": answer[:500], "citations": citations, "confidence": confidence}
        )
        self._langfuse.flush()

    def _validate_merchant_id(self, merchant_id: str) -> str:
        cleaned = merchant_id.strip()
        if not cleaned:
            raise ValueError("merchant_id cannot be empty")
        return cleaned

    def _build_system_prompt(self) -> str:
        from datetime import datetime, timezone
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return (
            f"You are a grounded D2C business intelligence assistant. Today's date is {today} UTC. "
            "CRITICAL RULES: "
            "1. Never include any numbers, figures, percentages, or statistics in your response unless they come directly from a tool you called in this conversation. "
            "2. The merchant_id is always automatically injected into every tool call — never ask the user for it. "
            "3. When the user mentions relative dates like 'this week', 'last 7 days', 'this month', 'today' — resolve them to ISO 8601 dates yourself using today's date and call the tool immediately. Do not ask the user for dates. "
            "4. Always call the relevant tool immediately when data is requested. Do not ask clarifying questions about merchant_id or dates. "
            "5. For greetings or non-data questions, respond in plain text with zero numeric claims. "
            "6. Keep responses concise and factual. "
            "Example: if asked 'what was my revenue this week', immediately call get_metric_summary with metric_name=revenue, start_date=7 days ago, end_date=today."
        )

    def _build_gemini_schema(self, schema: dict[str, Any]) -> types.Schema:
        type_map = {
            "object": types.Type.OBJECT,
            "string": types.Type.STRING,
            "integer": types.Type.INTEGER,
            "number": types.Type.NUMBER,
            "boolean": types.Type.BOOLEAN,
            "array": types.Type.ARRAY,
        }
        schema_type = type_map.get(schema.get("type", "string"), types.Type.STRING)
        properties: dict[str, types.Schema] = {}
        if "properties" in schema and isinstance(schema["properties"], dict):
            for prop_name, prop_schema in schema["properties"].items():
                properties[prop_name] = self._build_gemini_schema(prop_schema)
        return types.Schema(
            type=schema_type,
            description=schema.get("description", ""),
            enum=schema.get("enum") or None,
            properties=properties or None,
            required=schema.get("required") or None,
        )

    def _build_tools(self) -> list[types.Tool]:
        declarations = [
            types.FunctionDeclaration(
                name=t["name"],
                description=t["description"],
                parameters=self._build_gemini_schema(t["parameters"]),
            )
            for t in GEMINI_TOOLS_LIST
        ]
        return [types.Tool(function_declarations=declarations)]

    def _build_config(self) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            tools=self._build_tools(),
            system_instruction=self._build_system_prompt(),
        )

    def _compute_confidence(self, cited_values: list[CitedValue]) -> Literal["high", "medium", "low"]:
        if not cited_values:
            return "low"
        total_rows = sum(len(cv.source_row_ids) for cv in cited_values)
        if total_rows >= 5 and len(cited_values) >= 2:
            return "high"
        if total_rows >= 2:
            return "medium"
        return "low"

    def _extract_function_calls(self, response: Any) -> list[Any]:
        calls = []
        try:
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if part.function_call and part.function_call.name:
                        calls.append(part.function_call)
        except (AttributeError, IndexError, TypeError):
            pass
        return calls

    def _extract_text(self, response: Any) -> str:
        parts: list[str] = []
        try:
            for candidate in response.candidates:
                for part in candidate.content.parts:
                    if hasattr(part, "text") and part.text:
                        parts.append(part.text)
        except (AttributeError, IndexError, TypeError):
            pass
        return " ".join(p.strip() for p in parts if p.strip()).strip()

    def _model_content_from_response(self, response: Any) -> types.Content:
        try:
            return response.candidates[0].content
        except (AttributeError, IndexError):
            return types.Content(role="model", parts=[])

    def _row_to_cited_value(self, row: dict[str, Any]) -> CitedValue:
        return CitedValue(
            value=_normalize_decimal(row["value"]),
            currency=str(row.get("currency", "INR")),
            metric_name=str(row["metric_name"]),
            source_row_ids=[str(row["source_row_id"])],
            source=SourceType(str(row["source"])),
        )

    def _row_to_normalized_row(self, row: dict[str, Any]) -> NormalizedRow:
        return NormalizedRow(
            id=str(row["id"]),
            merchant_id=str(row["merchant_id"]),
            metric_name=MetricName(str(row["metric_name"])),
            value=_normalize_decimal(row["value"]),
            currency=str(row.get("currency", "INR")),
            dimensions=dict(row.get("dimensions") or {}),
            occurred_at=_ensure_timezone_aware(
                datetime.fromisoformat(str(row["occurred_at"]).replace("Z", "+00:00")),
                "occurred_at",
            ),
            provenance=Provenance(
                source=SourceType(str(row["source"])),
                source_row_id=str(row["source_row_id"]),
                source_url=row.get("source_url"),
                synced_at=_parse_iso_datetime(
                    row.get("synced_at") or datetime.now(timezone.utc).isoformat(),
                    "synced_at",
                ),
                raw_payload=row.get("raw_payload"),
            ),
        )

    def _rows_to_cited_values(self, rows: list[dict[str, Any]]) -> list[CitedValue]:
        cited = [self._row_to_cited_value(r) for r in rows]
        validate_cited_values(cited)
        return cited

    def _aggregate_rows_to_cited_value(
        self,
        rows: list[NormalizedRow],
        metric_name: str,
        operation: str,
        source: SourceType,
        value: Decimal,
        currency: str,
    ) -> tuple[CitedValue, dict[str, Any]]:
        trace = build_citation_trace(rows=rows, metric_name=metric_name, operation=operation)
        cited = CitedValue(
            value=value, currency=currency, metric_name=metric_name,
            source_row_ids=trace.source_row_ids, source=source,
        )
        return cited, trace.model_dump()

    def _extract_cited_values(self, tool_result: dict[str, Any]) -> list[CitedValue]:
        cited: list[CitedValue] = []
        raw = tool_result.get("cited_values")
        if isinstance(raw, list) and raw:
            for cv in raw:
                cited.append(cv if isinstance(cv, CitedValue) else CitedValue.model_validate(cv))
            validate_cited_values(cited)
            return cited
        raw_result = tool_result.get("result")
        if isinstance(raw_result, dict):
            rows = raw_result.get("rows")
            if isinstance(rows, list) and rows:
                return self._rows_to_cited_values(rows)
        return cited

    def _make_function_response_part(self, name: str, result: dict[str, Any]) -> types.Part:
        serializable = json.loads(json.dumps(result.get("result", {}), default=str))
        return types.Part(
            function_response=types.FunctionResponse(name=name, response={"output": serializable})
        )

    async def _handle_query_metrics(self, merchant_id: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        metric_name = MetricName(str(tool_input["metric_name"]))
        start_date = _ensure_timezone_aware(datetime.fromisoformat(str(tool_input["start_date"]).replace("Z", "+00:00")), "start_date")
        end_date = _ensure_timezone_aware(datetime.fromisoformat(str(tool_input["end_date"]).replace("Z", "+00:00")), "end_date")
        limit = int(tool_input.get("limit") or 100)
        rows = await self.metrics_service.repository.get_metric_rows(
            merchant_id=merchant_id, metric_name=metric_name, start_date=start_date, end_date=end_date)
        if not rows:
            raise CitationValidationError("No metric rows available for grounding")
        limited = rows[:limit]
        cited_values = self._rows_to_cited_values(limited)
        citation_trace = build_citation_trace(
            rows=[self._row_to_normalized_row(r) for r in limited],
            metric_name=metric_name.value, operation="query_metrics").model_dump(mode="python")
        return {"rows": limited, "row_count": len(limited), "metric_name": metric_name.value,
                "start_date": start_date, "end_date": end_date,
                "cited_values": cited_values, "citation_trace": citation_trace}

    async def _handle_get_metric_summary(self, merchant_id: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        metric_name = MetricName(str(tool_input["metric_name"]))
        start_date = _ensure_timezone_aware(datetime.fromisoformat(str(tool_input["start_date"]).replace("Z", "+00:00")), "start_date")
        end_date = _ensure_timezone_aware(datetime.fromisoformat(str(tool_input["end_date"]).replace("Z", "+00:00")), "end_date")
        rows = await self.metrics_service.repository.get_metric_rows(
            merchant_id=merchant_id, metric_name=metric_name, start_date=start_date, end_date=end_date)
        if not rows:
            raise CitationValidationError("No metric rows available for grounding")
        total = sum((_normalize_decimal(r.get("value", 0)) for r in rows), Decimal("0"))
        cited_value, citation_trace = self._aggregate_rows_to_cited_value(
            rows=[self._row_to_normalized_row(r) for r in rows],
            metric_name=metric_name.value, operation="get_metric_summary",
            source=SourceType(rows[0]["source"]), value=total, currency=str(rows[0].get("currency", "INR")))
        return {"metric_name": metric_name.value, "total": total, "row_count": len(rows),
                "start_date": start_date, "end_date": end_date,
                "cited_values": [cited_value], "citation_trace": citation_trace}

    async def _handle_compare_metric_periods(self, merchant_id: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        metric_name = MetricName(str(tool_input["metric_name"]))
        current_start = _ensure_timezone_aware(datetime.fromisoformat(str(tool_input["current_start"]).replace("Z", "+00:00")), "current_start")
        current_end = _ensure_timezone_aware(datetime.fromisoformat(str(tool_input["current_end"]).replace("Z", "+00:00")), "current_end")
        previous_start = _ensure_timezone_aware(datetime.fromisoformat(str(tool_input["previous_start"]).replace("Z", "+00:00")), "previous_start")
        previous_end = _ensure_timezone_aware(datetime.fromisoformat(str(tool_input["previous_end"]).replace("Z", "+00:00")), "previous_end")
        comparison = await self.metrics_service.compare_metric_periods(
            merchant_id=merchant_id, metric_name=metric_name,
            current_start=current_start, current_end=current_end,
            previous_start=previous_start, previous_end=previous_end)
        current_rows = await self.metrics_service.repository.get_metric_rows(
            merchant_id=merchant_id, metric_name=metric_name, start_date=current_start, end_date=current_end)
        previous_rows = await self.metrics_service.repository.get_metric_rows(
            merchant_id=merchant_id, metric_name=metric_name, start_date=previous_start, end_date=previous_end)
        if not current_rows or not previous_rows:
            raise CitationValidationError("No metric rows available for grounded comparison")
        current_cv, current_trace = self._aggregate_rows_to_cited_value(
            rows=[self._row_to_normalized_row(r) for r in current_rows],
            metric_name=metric_name.value, operation="compare_metric_periods_current",
            source=SourceType(current_rows[0]["source"]), value=comparison["current_value"],
            currency=str(current_rows[0].get("currency", "INR")))
        previous_cv, previous_trace = self._aggregate_rows_to_cited_value(
            rows=[self._row_to_normalized_row(r) for r in previous_rows],
            metric_name=metric_name.value, operation="compare_metric_periods_previous",
            source=SourceType(previous_rows[0]["source"]), value=comparison["previous_value"],
            currency=str(previous_rows[0].get("currency", "INR")))
        return {**comparison, "current_trace": current_trace, "previous_trace": previous_trace,
                "cited_values": [current_cv, previous_cv],
                "citation_trace": {"current_trace": current_trace, "previous_trace": previous_trace}}

    async def _handle_get_campaign_performance(self, merchant_id: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        start_date = _ensure_timezone_aware(datetime.fromisoformat(str(tool_input["start_date"]).replace("Z", "+00:00")), "start_date")
        end_date = _ensure_timezone_aware(datetime.fromisoformat(str(tool_input["end_date"]).replace("Z", "+00:00")), "end_date")
        limit = int(tool_input.get("limit") or 100)
        summary = await self.metrics_service.get_campaign_performance_summary(
            merchant_id=merchant_id, start_date=start_date, end_date=end_date)
        campaigns = summary.get("campaigns", [])[:limit]
        if not campaigns:
            raise CitationValidationError("No campaign rows available for grounding")
        source_row_ids = sorted({row_id for c in campaigns for row_id in c.get("source_row_ids", []) if str(row_id).strip()})
        citation_context = await self.metrics_service.build_citation_context(merchant_id=merchant_id, source_row_ids=source_row_ids)
        normalized_rows = [self._row_to_normalized_row(r) for r in citation_context]
        row_ids = [r.provenance.source_row_id for r in normalized_rows] or source_row_ids
        cited_values = [
            CitedValue(value=_normalize_decimal(summary.get("total_spend", Decimal("0"))), currency="INR", metric_name="ad_spend", source_row_ids=row_ids, source=SourceType.META_ADS),
            CitedValue(value=_normalize_decimal(summary.get("total_impressions", Decimal("0"))), currency="COUNT", metric_name="impressions", source_row_ids=row_ids, source=SourceType.META_ADS),
            CitedValue(value=_normalize_decimal(summary.get("total_clicks", Decimal("0"))), currency="COUNT", metric_name="clicks", source_row_ids=row_ids, source=SourceType.META_ADS),
        ]
        validate_cited_values(cited_values)
        citation_trace = build_citation_trace(rows=normalized_rows, metric_name="campaign_performance", operation="get_campaign_performance").model_dump(mode="python")
        return {**summary, "campaigns": campaigns, "limit": limit, "cited_values": cited_values, "citation_trace": citation_trace}

    async def _handle_get_roas_summary(self, merchant_id: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        start_date = _ensure_timezone_aware(datetime.fromisoformat(str(tool_input["start_date"]).replace("Z", "+00:00")), "start_date")
        end_date = _ensure_timezone_aware(datetime.fromisoformat(str(tool_input["end_date"]).replace("Z", "+00:00")), "end_date")
        summary = await self.metrics_service.get_roas_summary(merchant_id=merchant_id, start_date=start_date, end_date=end_date)
        revenue_rows = await self.metrics_service.repository.get_metric_rows(merchant_id=merchant_id, metric_name=MetricName.REVENUE, start_date=start_date, end_date=end_date)
        ad_spend_rows = await self.metrics_service.repository.get_metric_rows(merchant_id=merchant_id, metric_name=MetricName.AD_SPEND, start_date=start_date, end_date=end_date)
        if not revenue_rows or not ad_spend_rows:
            raise CitationValidationError("No metric rows available for grounded ROAS summary")
        revenue_context = [self._row_to_normalized_row(r) for r in revenue_rows]
        ad_spend_context = [self._row_to_normalized_row(r) for r in ad_spend_rows]
        cited_values = [
            CitedValue(value=_normalize_decimal(summary["revenue"]), currency=str(revenue_rows[0].get("currency", "INR")), metric_name="revenue", source_row_ids=[r.provenance.source_row_id for r in revenue_context], source=SourceType(str(revenue_rows[0]["source"]))),
            CitedValue(value=_normalize_decimal(summary["ad_spend"]), currency=str(ad_spend_rows[0].get("currency", "INR")), metric_name="ad_spend", source_row_ids=[r.provenance.source_row_id for r in ad_spend_context], source=SourceType(str(ad_spend_rows[0]["source"]))),
        ]
        validate_cited_values(cited_values)
        citation_trace = build_citation_trace(rows=revenue_context + ad_spend_context, metric_name="roas", operation="get_roas_summary").model_dump(mode="python")
        return {**summary, "cited_values": cited_values, "citation_trace": citation_trace}

    async def _handle_trigger_watchdog(self, merchant_id: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        from backend.agents.ad_watchdog import AdWatchdogAgent
        from backend.core.database import save_agent_log

        agent = AdWatchdogAgent()
        result = await agent.execute(merchant_id)
        agent_log = agent.build_agent_log(merchant_id=merchant_id, result=result)
        await save_agent_log(agent_log)

        cited_values = result.cited_values[:3] if result.cited_values else []

        return {
            "wrote_to": "agent_run_logs",
            "log_id": agent_log.id,
            "status": agent_log.status,
            "proposed_action": agent_log.proposed_action,
            "observation": agent_log.observation,
            "estimated_saving_inr": str(agent_log.estimated_saving_inr) if agent_log.estimated_saving_inr else None,
            "cited_values": cited_values,
        }

    _TOOL_DISPATCH: dict[str, str] = {
        "query_metrics": "_handle_query_metrics",
        "get_metric_summary": "_handle_get_metric_summary",
        "compare_metric_periods": "_handle_compare_metric_periods",
        "get_campaign_performance": "_handle_get_campaign_performance",
        "get_roas_summary": "_handle_get_roas_summary",
        "trigger_watchdog": "_handle_trigger_watchdog",
    }

    async def _execute_tool(self, merchant_id: str, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
        handler_name = self._TOOL_DISPATCH.get(tool_name)
        if not handler_name:
            raise ValueError(f"Unknown tool requested: {tool_name}")
        handler = getattr(self, handler_name)
        log = self.logger.bind(merchant_id=merchant_id, tool_name=tool_name)
        result = await handler(merchant_id, tool_input)
        cited_values = result.pop("cited_values", [])
        log.info("tool_executed", tool_name=tool_name, cited_values=len(cited_values))
        return {"tool_name": tool_name, "result": result, "cited_values": cited_values}

    async def _run_tool_loop(self, merchant_id: str, user_query: str) -> tuple[str, list[CitedValue]]:
        config = self._build_config()
        log = self.logger.bind(merchant_id=merchant_id)
        contents: list[types.Content] = [types.Content(role="user", parts=[types.Part(text=user_query)])]
        collected_cited_values: list[CitedValue] = []
        response: Any = None

        for iteration in range(self.max_tool_iterations):
            response = await asyncio.wait_for(
                asyncio.to_thread(self.client.models.generate_content, model=self.model_name, contents=contents, config=config),
                timeout=self.request_timeout_seconds,
            )
            function_calls = self._extract_function_calls(response)

            if not function_calls:
                answer = self._extract_text(response)
                if not answer.strip():
                    raise CitationValidationError("AI answer cannot be empty")
                return answer, collected_cited_values

            contents.append(self._model_content_from_response(response))
            function_response_parts: list[types.Part] = []
            for fc in function_calls:
                tool_input = dict(fc.args)
                tool_input["merchant_id"] = merchant_id
                tool_result = await self._execute_tool(merchant_id, fc.name, tool_input)
                collected_cited_values.extend(self._extract_cited_values(tool_result))
                function_response_parts.append(self._make_function_response_part(fc.name, tool_result))

            contents.append(types.Content(role="user", parts=function_response_parts))
            log.info("tool_loop_iteration_completed", iteration=iteration + 1, tool_calls=len(function_calls), citations=len(collected_cited_values))

        raise RuntimeError("Max tool iterations exceeded")

    async def generate_grounded_response_stream(self, merchant_id: str, user_query: str) -> AsyncIterator[dict[str, Any]]:
        normalized_merchant_id = self._validate_merchant_id(merchant_id)
        log = self.logger.bind(merchant_id=normalized_merchant_id)
        config = self._build_config()
        contents: list[types.Content] = [types.Content(role="user", parts=[types.Part(text=user_query)])]
        collected_cited_values: list[CitedValue] = []
        response: Any = None
        lf_trace = self._lf_trace(normalized_merchant_id, user_query)

        for iteration in range(self.max_tool_iterations):
            response = await asyncio.wait_for(
                asyncio.to_thread(self.client.models.generate_content, model=self.model_name, contents=contents, config=config),
                timeout=self.request_timeout_seconds,
            )
            function_calls = self._extract_function_calls(response)

            if not function_calls:
                break

            yield {"type": "processing", "message": f"Fetching data (step {iteration + 1})..."}
            contents.append(self._model_content_from_response(response))
            function_response_parts: list[types.Part] = []
            for fc in function_calls:
                tool_input = dict(fc.args)
                tool_input["merchant_id"] = normalized_merchant_id
                tool_result = await self._execute_tool(normalized_merchant_id, fc.name, tool_input)
                collected_cited_values.extend(self._extract_cited_values(tool_result))
                function_response_parts.append(self._make_function_response_part(fc.name, tool_result))
            contents.append(types.Content(role="user", parts=function_response_parts))
            log.info("stream_tool_loop_iteration", iteration=iteration + 1, citations=len(collected_cited_values))

        if response is None:
            yield {"type": "error", "message": "No response from model"}
            yield {"type": "done"}
            return

        # Use the async streaming API for real token-by-token delivery.
        # Falls back to the already-retrieved non-streaming response on any error.
        final_text = ""
        try:
            async for chunk in self.client.aio.models.generate_content_stream(
                model=self.model_name,
                contents=contents,
                config=config,
            ):
                token = chunk.text or ""
                if token:
                    final_text += token
                    yield {"type": "token", "token": token}
        except Exception as exc:
            log.warning("stream_api_fallback", error=str(exc))
            final_text = self._extract_text(response)
            if final_text:
                for i in range(0, len(final_text), 15):
                    yield {"type": "token", "token": final_text[i:i + 15]}
                    await asyncio.sleep(0.02)

        if not final_text.strip():
            yield {"type": "error", "message": "AI answer cannot be empty"}
            yield {"type": "done"}
            return

        if collected_cited_values:
            try:
                enforce_grounded_response(answer=final_text, cited_values=collected_cited_values)
            except CitationValidationError as exc:
                yield {"type": "error", "message": str(exc)}
                yield {"type": "done"}
                return

        confidence = self._compute_confidence(collected_cited_values)
        yield {"type": "citations", "citations": [cv.citation_summary() for cv in collected_cited_values]}
        yield {"type": "confidence", "confidence": confidence}
        yield {"type": "done"}
        self._lf_finish(lf_trace, final_text, len(collected_cited_values), confidence)
        log.info("grounded_stream_completed", citations=len(collected_cited_values), confidence=confidence)

    async def generate_grounded_response(self, merchant_id: str, user_query: str) -> ChatResponse:
        normalized_merchant_id = self._validate_merchant_id(merchant_id)
        log = self.logger.bind(merchant_id=normalized_merchant_id)
        answer, cited_values = await self._run_tool_loop(merchant_id=normalized_merchant_id, user_query=user_query)
        enforce_grounded_response(answer=answer, cited_values=cited_values)
        confidence = self._compute_confidence(cited_values)
        response = ChatResponse(answer=answer, cited_values=cited_values, confidence=confidence)
        log.info("grounded_response_generated", citations=len(cited_values), confidence=confidence)
        return response
