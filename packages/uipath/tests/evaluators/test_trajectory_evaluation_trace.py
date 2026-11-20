from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from uipath.eval.models.models import TrajectoryEvaluationTrace


def _record_parent_child_spans() -> list[ReadableSpan]:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer(__name__)

    with tracer.start_as_current_span("parent"):
        with tracer.start_as_current_span("child") as child:
            child.set_attribute("tool.name", "search")

    return list(exporter.get_finished_spans())


class TestTrajectoryEvaluationTraceFromReadableSpans:
    def test_resolves_parent_names(self) -> None:
        trace = TrajectoryEvaluationTrace.from_readable_spans(
            _record_parent_child_spans()
        )

        by_name = {span.name: span for span in trace.spans}
        assert by_name["child"].parent_name == "parent"
        assert by_name["child"].attributes == {"tool.name": "search"}
        assert by_name["parent"].parent_name is None

    def test_span_without_context_is_kept_but_not_a_parent(self) -> None:
        spans = [*_record_parent_child_spans(), ReadableSpan(name="orphan")]

        trace = TrajectoryEvaluationTrace.from_readable_spans(spans)

        assert [span.name for span in trace.spans] == ["child", "parent", "orphan"]
        assert trace.spans[2].parent_name is None
