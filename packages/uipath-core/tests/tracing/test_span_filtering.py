"""Tests for span filtering in trace manager and processors."""

from opentelemetry import trace

from uipath.core.tracing.trace_manager import UiPathTraceManager
from uipath.core.tracing.types import UiPathTraceSettings


class TestSpanFiltering:
    """Tests for span filtering functionality."""

    def test_no_filter_exports_all_spans(self):
        """Test that without a filter, all spans are exported."""
        trace_manager = UiPathTraceManager()

        tracer = trace.get_tracer("test")
        with trace_manager.start_execution_span("root", "exec-1"):
            with tracer.start_as_current_span("child-1"):
                pass
            with tracer.start_as_current_span("child-2"):
                pass

        spans = trace_manager.get_execution_spans("exec-1")
        assert len(spans) == 3
        span_names = {s.name for s in spans}
        assert span_names == {"root", "child-1", "child-2"}

    def test_filter_drops_non_matching_spans(self):
        """Test that filter drops spans that don't match the predicate."""
        from unittest.mock import MagicMock

        from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

        mock_exporter = MagicMock(spec=SpanExporter)
        mock_exporter.export.return_value = SpanExportResult.SUCCESS

        settings = UiPathTraceSettings(
            span_filter=lambda span: (
                span.attributes is not None and span.attributes.get("keep") is True
            )
        )
        trace_manager = UiPathTraceManager()
        trace_manager.add_span_exporter(mock_exporter, batch=False, settings=settings)

        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("kept", attributes={"keep": True}):
            pass
        with tracer.start_as_current_span("dropped", attributes={"keep": False}):
            pass
        with tracer.start_as_current_span("also-dropped"):
            pass

        trace_manager.flush_spans()

        exported_spans = []
        for call in mock_exporter.export.call_args_list:
            exported_spans.extend(call[0][0])

        exported_names = {s.name for s in exported_spans}
        assert "kept" in exported_names
        assert "dropped" not in exported_names
        assert "also-dropped" not in exported_names

    def test_filter_by_span_name(self):
        """Test filtering spans by name pattern."""
        from unittest.mock import MagicMock

        from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

        mock_exporter = MagicMock(spec=SpanExporter)
        mock_exporter.export.return_value = SpanExportResult.SUCCESS

        settings = UiPathTraceSettings(
            span_filter=lambda span: span.name.startswith("uipath.")
        )
        trace_manager = UiPathTraceManager()
        trace_manager.add_span_exporter(mock_exporter, batch=False, settings=settings)

        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("uipath.action"):
            pass
        with tracer.start_as_current_span("uipath.tool"):
            pass
        with tracer.start_as_current_span("http.request"):
            pass

        trace_manager.flush_spans()

        exported_spans = []
        for call in mock_exporter.export.call_args_list:
            exported_spans.extend(call[0][0])

        exported_names = {s.name for s in exported_spans}
        assert "uipath.action" in exported_names
        assert "uipath.tool" in exported_names
        assert "http.request" not in exported_names

    def test_filter_custom_instrumentation_attribute(self):
        """Test filtering by custom instrumentation attribute (low-code scenario)."""
        from unittest.mock import MagicMock

        from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

        mock_exporter = MagicMock(spec=SpanExporter)
        mock_exporter.export.return_value = SpanExportResult.SUCCESS

        settings = UiPathTraceSettings(
            span_filter=lambda span: bool(
                span.attributes and span.attributes.get("uipath.custom_instrumentation")
            )
        )
        trace_manager = UiPathTraceManager()
        trace_manager.add_span_exporter(mock_exporter, batch=False, settings=settings)

        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span(
            "custom-span",
            attributes={"uipath.custom_instrumentation": True},
        ):
            pass
        with tracer.start_as_current_span(
            "auto-instrumented",
            attributes={"http.method": "GET"},
        ):
            pass

        trace_manager.flush_spans()

        exported_spans = []
        for call in mock_exporter.export.call_args_list:
            exported_spans.extend(call[0][0])

        exported_names = {s.name for s in exported_spans}
        assert "custom-span" in exported_names
        assert "auto-instrumented" not in exported_names

    def test_none_filter_same_as_no_filter(self):
        """Test that explicit None filter behaves same as no filter."""
        from unittest.mock import MagicMock

        from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

        mock_exporter = MagicMock(spec=SpanExporter)
        mock_exporter.export.return_value = SpanExportResult.SUCCESS

        settings = UiPathTraceSettings(span_filter=None)
        trace_manager = UiPathTraceManager()
        trace_manager.add_span_exporter(mock_exporter, batch=False, settings=settings)

        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("span-1"):
            pass
        with tracer.start_as_current_span("span-2"):
            pass

        trace_manager.flush_spans()

        exported_spans = []
        for call in mock_exporter.export.call_args_list:
            exported_spans.extend(call[0][0])

        assert len(exported_spans) == 2

    def test_filter_with_empty_attributes(self):
        """Test that filter handles spans with no attributes gracefully."""
        from unittest.mock import MagicMock

        from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

        mock_exporter = MagicMock(spec=SpanExporter)
        mock_exporter.export.return_value = SpanExportResult.SUCCESS

        settings = UiPathTraceSettings(
            span_filter=lambda span: (
                span.attributes is not None and span.attributes.get("required") is True
            )
        )
        trace_manager = UiPathTraceManager()
        trace_manager.add_span_exporter(mock_exporter, batch=False, settings=settings)

        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("no-attrs"):
            pass
        with tracer.start_as_current_span(
            "has-required", attributes={"required": True}
        ):
            pass

        trace_manager.flush_spans()

        exported_spans = []
        for call in mock_exporter.export.call_args_list:
            exported_spans.extend(call[0][0])

        exported_names = {s.name for s in exported_spans}
        assert "has-required" in exported_names
        assert "no-attrs" not in exported_names

    def test_different_filters_per_exporter(self):
        """Test that different exporters can have different filters."""
        from unittest.mock import MagicMock

        from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

        mock_exporter_a = MagicMock(spec=SpanExporter)
        mock_exporter_a.export.return_value = SpanExportResult.SUCCESS

        mock_exporter_b = MagicMock(spec=SpanExporter)
        mock_exporter_b.export.return_value = SpanExportResult.SUCCESS

        settings_a = UiPathTraceSettings(
            span_filter=lambda span: (
                span.attributes is not None and span.attributes.get("dest") == "a"
            )
        )
        settings_b = UiPathTraceSettings(
            span_filter=lambda span: (
                span.attributes is not None and span.attributes.get("dest") == "b"
            )
        )

        trace_manager = UiPathTraceManager()
        trace_manager.add_span_exporter(
            mock_exporter_a, batch=False, settings=settings_a
        )
        trace_manager.add_span_exporter(
            mock_exporter_b, batch=False, settings=settings_b
        )

        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("to-a", attributes={"dest": "a"}):
            pass
        with tracer.start_as_current_span("to-b", attributes={"dest": "b"}):
            pass
        with tracer.start_as_current_span("to-neither", attributes={"dest": "c"}):
            pass

        trace_manager.flush_spans()

        exported_a = []
        for call in mock_exporter_a.export.call_args_list:
            exported_a.extend(call[0][0])
        assert {s.name for s in exported_a} == {"to-a"}

        exported_b = []
        for call in mock_exporter_b.export.call_args_list:
            exported_b.extend(call[0][0])
        assert {s.name for s in exported_b} == {"to-b"}
