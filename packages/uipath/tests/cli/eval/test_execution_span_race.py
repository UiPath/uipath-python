"""Reproduces the UV-16309 intermittent-empty-AgentRunHistory race.

`ExecutionSpanProcessor` (eval/runtime/_exporters.py) is a real OTel
`BatchSpanProcessor`: `on_end()` only queues a span, it does not export it.
`ExecutionSpanExporter.get_spans()` (read by `trace_to_str()` to build
`AgentRunHistory`) only sees spans that have already reached `export()`.

Production flushes the queue via `UiPathTraceManager.flush_spans()` (called
from `uipath-runtime`'s `UiPathExecutionRuntime.execute()` finally block, and
from `start_execution_span`'s finally block) right as the root execution span
ends. That flush only catches spans whose `on_end()` already fired by that
moment. A tool-call span that legitimately ends *after* the root span (e.g. a
background/detached task finishing a beat late) is queued but not yet
exported, so a read of `get_spans()` taken between "root span ended" and
"next flush" sees a real, completed tool call as if it never happened -
exactly the "history genuinely exists but AgentRunHistory is empty,
intermittently" symptom.

The fix in `_get_and_clear_execution_data()` adds one more flush right before
the read, which closes the race for any span that has *already ended* by
read time - the common case, e.g. a tool call wrapped in a short-lived
background task. It does NOT close the race for a span belonging to a truly
detached task that is still running (has no `on_end()` yet) when the read
happens - there is no handle for the runtime to await in that case, and
closing it would require tracking/awaiting such tasks, which is a separate,
larger change than this one-line flush.
"""

import json

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider

from uipath.core.tracing import UiPathTraceManager
from uipath.eval._execution_context import ExecutionSpanCollector
from uipath.eval._helpers.evaluators_helpers import trace_to_str
from uipath.eval.runtime._exporters import (
    ExecutionLogsExporter,
    ExecutionSpanExporter,
    ExecutionSpanProcessor,
)
from uipath.eval.runtime.runtime import UiPathEvalRuntime

EXECUTION_ID = "exec-race-1"


def _pin_batch_schedule(processor: ExecutionSpanProcessor) -> None:
    """Stop the processor's own background worker from auto-exporting.

    `ExecutionSpanProcessor` is a real `BatchSpanProcessor` with its own
    background worker thread, which auto-flushes every 5s by default (or
    when its queue fills). Tests asserting "not yet exported at this exact
    moment" would otherwise flake if that worker thread woke up and exported
    on its own between a span ending and the assertion running. Pin the
    schedule delay far beyond any test's runtime so only an explicit
    `force_flush()`/`flush_spans()` call ever exports anything.
    """
    batch_processor = processor._batch_processor
    batch_processor._schedule_delay_millis = 3600_000
    batch_processor._schedule_delay = 3600.0


def _make_processor() -> tuple[
    ExecutionSpanProcessor, ExecutionSpanExporter, trace.Tracer
]:
    exporter = ExecutionSpanExporter()
    collector = ExecutionSpanCollector()
    processor = ExecutionSpanProcessor(exporter, collector)
    _pin_batch_schedule(processor)

    provider = TracerProvider()
    provider.add_span_processor(processor)
    tracer = provider.get_tracer("test")

    return processor, exporter, tracer


def test_flush_only_exports_spans_ended_before_it_runs() -> None:
    """A late-ending tool span is invisible to get_spans() until the *next* flush."""
    processor, exporter, tracer = _make_processor()

    # Root execution span starts and ends (mirrors start_execution_span's `with` block).
    with tracer.start_as_current_span(
        "root", attributes={"execution.id": EXECUTION_ID}
    ):
        pass

    # Mirrors flush_spans() firing right as the root span's context manager exits.
    processor.force_flush()

    assert [s.name for s in exporter.get_spans(EXECUTION_ID)] == ["root"]

    # A tool-call span that genuinely happened, but whose on_end() only fires
    # *after* the flush above - e.g. a detached/background task that outlives
    # the awaited delegate.execute() call.
    with tracer.start_as_current_span(
        "tool_call", attributes={"execution.id": EXECUTION_ID, "tool.name": "search"}
    ):
        pass

    # This is the moment _get_and_clear_execution_data() reads spans in
    # eval/runtime/runtime.py: no flush has happened since the tool span ended.
    spans_at_read_time = exporter.get_spans(EXECUTION_ID)

    assert [s.name for s in spans_at_read_time] == ["root"], (
        "the tool-call span genuinely ended but is not yet exported - "
        "trace_to_str() would build an AgentRunHistory missing this real tool call"
    )

    # A subsequent flush (e.g. one added right before the read) makes it visible.
    processor.force_flush()
    assert {s.name for s in exporter.get_spans(EXECUTION_ID)} == {"root", "tool_call"}


def test_flush_immediately_before_read_closes_the_race() -> None:
    """Proposed fix: force_flush() right before get_spans() sees every ended span."""
    processor, exporter, tracer = _make_processor()

    with tracer.start_as_current_span(
        "root", attributes={"execution.id": EXECUTION_ID}
    ):
        with tracer.start_as_current_span(
            "tool_call",
            attributes={"execution.id": EXECUTION_ID, "tool.name": "search"},
        ):
            pass

    # A flush right before the read (unlike production today) picks up
    # everything that has ended by then, including the tool call.
    processor.force_flush()

    spans_at_read_time = exporter.get_spans(EXECUTION_ID)
    assert {s.name for s in spans_at_read_time} == {"root", "tool_call"}


def test_race_produces_empty_agent_run_history_for_a_real_tool_call() -> None:
    """Ties the exporter-level race to the actual UV-16309 symptom.

    trace_to_str() (used to build AgentRunHistory for the trajectory/LLM-judge
    evaluators) is handed exactly what get_spans() returns. If the read happens
    in the window between the root-span flush and the late tool span's own
    flush, the genuinely-completed tool call is silently dropped from the
    evaluator prompt - not because it didn't happen, but because it wasn't
    exported yet.
    """
    processor, exporter, tracer = _make_processor()

    with tracer.start_as_current_span(
        "root", attributes={"execution.id": EXECUTION_ID}
    ):
        pass
    processor.force_flush()

    with tracer.start_as_current_span(
        "tool_call",
        attributes={
            "execution.id": EXECUTION_ID,
            "tool.name": "search",
            # input.value/output.value are OTel span attributes: they must be
            # primitive/sequence-of-primitive values, so real spans always
            # carry a JSON-encoded string here, never a raw dict.
            "input.value": json.dumps({"query": "uipath"}),
            "output.value": "42 results",
        },
    ):
        pass

    # No flush here - mirrors _get_and_clear_execution_data() reading
    # immediately after the delegate returns, with nothing forcing the
    # late-ending tool span's export first.
    agent_run_history = trace_to_str(exporter.get_spans(EXECUTION_ID))
    assert agent_run_history == "", (
        "expected the unflushed tool call to be missing from AgentRunHistory, "
        "reproducing UV-16309's 'history genuinely exists but comes back empty' case"
    )

    # With the extra flush (the proposed fix) in place, the same real tool
    # call is captured correctly.
    processor.force_flush()
    agent_run_history_after_flush = trace_to_str(exporter.get_spans(EXECUTION_ID))
    assert "Tool: search" in agent_run_history_after_flush
    assert "42 results" in agent_run_history_after_flush


def test_get_and_clear_execution_data_flushes_before_reading() -> None:
    """Exercises the actual production method, not just a standalone processor.

    Builds the same trace_manager/span_exporter/span_collector/logs_exporter
    wiring UiPathEvalRuntime.__init__ sets up, then calls the real
    `_get_and_clear_execution_data` (unbound, via the class) against it. This
    fails without the `flush_spans()` line in that method - removing that
    line reproduces the empty-AgentRunHistory bug here directly, not just in
    the lower-level exporter tests above.
    """
    trace_manager = UiPathTraceManager()
    span_exporter = ExecutionSpanExporter()
    span_collector = ExecutionSpanCollector()
    span_processor = ExecutionSpanProcessor(span_exporter, span_collector)
    _pin_batch_schedule(span_processor)
    trace_manager.add_span_processor(span_processor)
    logs_exporter = ExecutionLogsExporter()

    fake_runtime = type(
        "FakeEvalRuntime",
        (),
        {
            "trace_manager": trace_manager,
            "span_exporter": span_exporter,
            "span_collector": span_collector,
            "logs_exporter": logs_exporter,
        },
    )()

    tracer = trace_manager.tracer_provider.get_tracer("test")
    with tracer.start_as_current_span(
        "root", attributes={"execution.id": EXECUTION_ID}
    ):
        pass
    # Root span's own flush (mirrors start_execution_span's finally block)
    # happens before the late tool call below - only the tool call is at risk.
    trace_manager.flush_spans()

    with tracer.start_as_current_span(
        "tool_call",
        attributes={"execution.id": EXECUTION_ID, "tool.name": "search"},
    ):
        pass

    spans, _logs = UiPathEvalRuntime._get_and_clear_execution_data(
        fake_runtime, EXECUTION_ID
    )

    assert {s.name for s in spans} == {"root", "tool_call"}
