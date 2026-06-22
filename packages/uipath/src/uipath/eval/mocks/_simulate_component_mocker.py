"""Mocker that routes tool calls through the simulate-component API."""

from __future__ import annotations

import logging
from typing import Any, Callable, cast

from pydantic import TypeAdapter

from uipath.platform.chat._llm_gateway_service import _cleanup_schema

from .._execution_context import execution_id_context, span_collector_context
from ._llm_mocker import LLMMocker
from ._mocker import (
    Mocker,
    R,
    T,
    UiPathMockResponseGenerationError,
    UiPathNoMockFoundError,
)
from ._simulate_component_service import _create_simulate_component_service
from ._types import ComponentSimulationConfig, MockingContext

logger = logging.getLogger(__name__)


class SimulateComponentMocker(Mocker):
    """Routes each tool call to the simulate-component API based on per-component config."""

    def __init__(self, context: MockingContext) -> None:
        self._context = context
        self._components: dict[str, ComponentSimulationConfig] = {
            c.component_id: c for c in (context.components or [])
        }
        self._normalized: dict[str, ComponentSimulationConfig] = {
            c.component_id.replace("_", " "): c for c in (context.components or [])
        }
        self._workload_id = context.workload_id or ""

    def _find_component(self, tool_name: str) -> ComponentSimulationConfig | None:
        return self._components.get(tool_name) or self._normalized.get(
            tool_name.replace("_", " ")
        )

    async def response(
        self,
        func: Callable[[T], R],
        params: dict[str, Any],
        invocation: tuple[tuple[Any, ...], dict[str, Any]],
    ) -> R:
        tool_name = params.get("name") or func.__name__
        component = self._find_component(tool_name)

        if component is None:
            raise UiPathNoMockFoundError(f"No simulation config for '{tool_name}'.")

        args, kwargs = invocation

        return_type: Any = func.__annotations__.get("return", None) or Any
        raw_output_schema = (
            params.get("output_schema") or TypeAdapter(return_type).json_schema()
        )
        output_schema = component.output_schema or _cleanup_schema(raw_output_schema)
        input_payload = {"args": list(args), "kwargs": kwargs}
        input_schema = component.input_schema or params.get("input_schema")

        execution_history = self._build_execution_history()
        trace_id, parent_span_id = self._get_span_context()
        workload_info = {
            "name": self._context.name,
            "userInput": self._context.inputs,
        }

        example_calls = [
            {"id": ex.id, "input": ex.input, "output": ex.output}
            for ex in (params.get("example_calls") or [])
        ]

        payload: dict[str, Any] = {
            "workloadId": self._workload_id,
            "componentId": component.component_id,
            "componentType": component.component_type or "tool",
            "componentDescription": component.component_description
            or params.get("description"),
            "input": input_payload,
            "inputSchema": input_schema,
            "outputSchema": output_schema,
            "simulationInstruction": component.simulation_instruction,
            "simulationStrategy": int(component.simulation_strategy),
            "mockValue": component.mock_value,
            "behaviors": (
                [b.model_dump() for b in component.behaviors]
                if component.behaviors
                else None
            ),
            "exampleCalls": example_calls or None,
            "executionHistory": execution_history or None,
            "workloadInfo": workload_info,
            "traceId": trace_id,
            "parentSpanId": parent_span_id,
        }

        logger.info("simulate-component: calling API for '%s'", tool_name)
        try:
            service = _create_simulate_component_service()
            result = await service.simulate(payload)
        except Exception as e:
            logger.error(
                "simulate-component: API call failed for '%s': %s", tool_name, e
            )
            raise UiPathMockResponseGenerationError(
                f"simulate-component API call failed for '{tool_name}'"
            ) from e

        status = result.get("status")
        if status == 1:  # Completed
            logger.info("simulate-component: '%s' simulated successfully", tool_name)
            return cast(R, result.get("simulatedOutput"))

        error = result.get("error") or {}
        error_message = error.get("message", f"Simulation failed for '{tool_name}'")
        logger.error("simulate-component: '%s' failed — %s", tool_name, error_message)
        raise UiPathMockResponseGenerationError(error_message)

    def _build_execution_history(self) -> str | None:
        span_collector = span_collector_context.get()
        execution_id = execution_id_context.get()
        if span_collector and execution_id:
            spans = span_collector.get_spans(execution_id)
            return LLMMocker.spans_to_llm_context(spans) if spans else None
        return None

    @staticmethod
    def _get_span_context() -> tuple[str | None, str | None]:
        """Return (traceId, parentSpanId) from the current OTel span, or (None, None)."""
        from opentelemetry import trace

        span_ctx = trace.get_current_span().get_span_context()
        if not span_ctx.is_valid:
            return None, None
        trace_id = f"{span_ctx.trace_id:032x}"
        span_id = f"{span_ctx.span_id:016x}"
        return trace_id, span_id
