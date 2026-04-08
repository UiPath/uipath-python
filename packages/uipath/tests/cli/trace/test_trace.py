"""Tests for the ``uipath trace`` CLI command."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from uipath._cli.cli_trace import (
    SpanNode,
    _build_tree,
    _build_tree_from_eval,
    _build_tree_from_jsonl,
    _count_spans,
    _detect_format,
    _filter_contains,
    _filter_tree,
    _load_eval_output_spans,
    _load_jsonl_spans,
    _parse_otel_time,
    _safe_parse_json,
    _span_label,
    _truncate,
    trace,
)

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_TRACE = FIXTURES / "sample_trace.jsonl"
SAMPLE_ERROR_TRACE = FIXTURES / "sample_error_trace.jsonl"
SAMPLE_EVAL_OUTPUT = FIXTURES / "sample_eval_output.json"
SAMPLE_EVAL_TRACE = FIXTURES / "sample_eval_trace.jsonl"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


class TestLoadJsonlSpans:
    def test_loads_all_spans(self):
        spans = _load_jsonl_spans(str(SAMPLE_TRACE))
        assert len(spans) == 4

    def test_span_has_expected_fields(self):
        spans = _load_jsonl_spans(str(SAMPLE_TRACE))
        root = spans[0]
        assert root["name"] == "agent"
        assert root["context"]["trace_id"] == "0x1234567890abcdef1234567890abcdef"
        assert root["parent_id"] is None

    def test_child_span_has_parent_id(self):
        spans = _load_jsonl_spans(str(SAMPLE_TRACE))
        llm_span = spans[1]
        assert llm_span["parent_id"] == "0x1111111111111111"

    def test_empty_file(self, tmp_path):
        empty = tmp_path / "empty.jsonl"
        empty.write_text("")
        spans = _load_jsonl_spans(str(empty))
        assert spans == []


class TestLoadEvalOutputSpans:
    def test_loads_spans_from_verbose_output(self):
        spans = _load_eval_output_spans(str(SAMPLE_EVAL_OUTPUT), eval_id=None)
        assert len(spans) == 2

    def test_filters_by_eval_id(self):
        spans = _load_eval_output_spans(
            str(SAMPLE_EVAL_OUTPUT), eval_id="test-weather-query"
        )
        assert len(spans) == 2
        assert all(s["_eval_name"] == "test-weather-query" for s in spans)

    def test_missing_eval_id_returns_empty(self):
        spans = _load_eval_output_spans(str(SAMPLE_EVAL_OUTPUT), eval_id="nonexistent")
        assert spans == []

    def test_eval_without_agent_output_skipped(self):
        # test-no-trace has agentExecutionOutput: null
        spans = _load_eval_output_spans(
            str(SAMPLE_EVAL_OUTPUT), eval_id="test-no-trace"
        )
        assert spans == []

    def test_normalised_span_has_parent_name(self):
        spans = _load_eval_output_spans(str(SAMPLE_EVAL_OUTPUT), eval_id=None)
        tool_span = [s for s in spans if s["name"] == "get_weather"][0]
        assert tool_span["parent_name"] == "agent"


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------


class TestDetectFormat:
    def test_jsonl_by_extension(self, tmp_path):
        f = tmp_path / "traces.jsonl"
        f.write_text("{}\n")
        assert _detect_format(str(f)) == "jsonl"

    def test_eval_json_detected(self):
        assert _detect_format(str(SAMPLE_EVAL_OUTPUT)) == "eval_json"

    def test_json_without_eval_keys_is_jsonl(self, tmp_path):
        f = tmp_path / "data.json"
        f.write_text('{"name": "something"}\n')
        assert _detect_format(str(f)) == "jsonl"


# ---------------------------------------------------------------------------
# Tree building
# ---------------------------------------------------------------------------


class TestBuildTreeJsonl:
    def test_builds_correct_hierarchy(self):
        spans = _load_jsonl_spans(str(SAMPLE_TRACE))
        roots = _build_tree_from_jsonl(spans)
        assert len(roots) == 1
        root = roots[0]
        assert root.name == "agent"
        assert len(root.children) == 3  # 2 LLM + 1 tool

    def test_root_has_no_parent(self):
        spans = _load_jsonl_spans(str(SAMPLE_TRACE))
        roots = _build_tree_from_jsonl(spans)
        assert roots[0].span.get("parent_id") is None

    def test_children_are_correct(self):
        spans = _load_jsonl_spans(str(SAMPLE_TRACE))
        roots = _build_tree_from_jsonl(spans)
        child_names = sorted([c.name for c in roots[0].children])
        assert child_names == ["ChatOpenAI", "ChatOpenAI", "get_weather"]


class TestBuildTreeEval:
    def test_builds_hierarchy_from_parent_name(self):
        spans = _load_eval_output_spans(str(SAMPLE_EVAL_OUTPUT), eval_id=None)
        roots = _build_tree_from_eval(spans)
        assert len(roots) == 1
        root = roots[0]
        assert root.name == "agent"
        assert len(root.children) == 1
        assert root.children[0].name == "get_weather"


class TestBuildTree:
    def test_dispatches_to_jsonl(self):
        spans = _load_jsonl_spans(str(SAMPLE_TRACE))
        roots = _build_tree(spans, is_eval=False)
        assert len(roots) == 1

    def test_dispatches_to_eval(self):
        spans = _load_eval_output_spans(str(SAMPLE_EVAL_OUTPUT), eval_id=None)
        roots = _build_tree(spans, is_eval=True)
        assert len(roots) == 1


# ---------------------------------------------------------------------------
# SpanNode properties
# ---------------------------------------------------------------------------


class TestSpanNode:
    def test_status_ok(self):
        node = SpanNode({"status": {"status_code": "OK"}})
        assert node.status_code == "OK"
        assert "✓" in node.status_icon

    def test_status_error(self):
        node = SpanNode({"status": {"status_code": "ERROR"}})
        assert node.status_code == "ERROR"
        assert "✗" in node.status_icon

    def test_status_unset(self):
        node = SpanNode({"status": {}})
        assert node.status_code == "UNSET"
        assert "○" in node.status_icon

    def test_duration_calculation(self):
        node = SpanNode(
            {
                "start_time": "2024-01-15T10:30:00.000000Z",
                "end_time": "2024-01-15T10:30:02.300000Z",
            }
        )
        assert node.duration_ms == pytest.approx(2300, abs=1)
        assert node.duration_str == "2.3s"

    def test_duration_ms_range(self):
        node = SpanNode(
            {
                "start_time": "2024-01-15T10:30:00.000000Z",
                "end_time": "2024-01-15T10:30:00.500000Z",
            }
        )
        assert node.duration_str == "500ms"

    def test_duration_no_timestamps(self):
        node = SpanNode({})
        assert node.duration_ms is None
        assert node.duration_str == ""

    def test_attributes(self):
        node = SpanNode({"attributes": {"foo": "bar"}})
        assert node.attributes == {"foo": "bar"}

    def test_span_type(self):
        node = SpanNode({"attributes": {"span_type": "TOOL"}})
        assert node.span_type == "TOOL"

    def test_events(self):
        events = [{"name": "exception", "attributes": {"exception.type": "ValueError"}}]
        node = SpanNode({"events": events})
        assert node.events == events


# ---------------------------------------------------------------------------
# Span label
# ---------------------------------------------------------------------------


class TestSpanLabel:
    def test_llm_span_with_model(self):
        node = SpanNode(
            {"name": "ChatOpenAI", "attributes": {"llm.model_name": "gpt-4o"}}
        )
        assert _span_label(node) == "LLM (gpt-4o)"

    def test_llm_span_by_kind(self):
        node = SpanNode(
            {
                "name": "completion",
                "attributes": {"openinference.span.kind": "LLM"},
            }
        )
        assert _span_label(node) == "LLM call"

    def test_tool_span(self):
        node = SpanNode(
            {
                "name": "get_weather",
                "attributes": {
                    "span_type": "TOOL",
                    "tool.name": "get_weather",
                },
            }
        )
        label = _span_label(node)
        assert "get_weather" in label
        assert "🔧" in label

    def test_generic_span(self):
        node = SpanNode({"name": "my_function", "attributes": {}})
        assert _span_label(node) == "my_function"


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


class TestFilterTree:
    def _build_sample_tree(self):
        spans = _load_jsonl_spans(str(SAMPLE_TRACE))
        return _build_tree_from_jsonl(spans)

    def test_no_filter_returns_all(self):
        roots = self._build_sample_tree()
        filtered = _filter_tree(roots)
        assert _count_spans(filtered) == 4

    def test_filter_by_name(self):
        roots = self._build_sample_tree()
        filtered = _filter_tree(roots, name_pattern="get_weather")
        # Should keep root (ancestor) + the matching span
        assert _count_spans(filtered) >= 1
        # The matching span should be in the tree
        names = _collect_names(filtered)
        assert "get_weather" in names

    def test_filter_by_name_glob(self):
        roots = self._build_sample_tree()
        filtered = _filter_tree(roots, name_pattern="Chat*")
        names = _collect_names(filtered)
        assert "ChatOpenAI" in names

    def test_filter_by_span_type(self):
        roots = self._build_sample_tree()
        filtered = _filter_tree(roots, span_type_filter="TOOL")
        names = _collect_names(filtered)
        assert "get_weather" in names

    def test_filter_by_status(self):
        spans = _load_jsonl_spans(str(SAMPLE_ERROR_TRACE))
        roots = _build_tree_from_jsonl(spans)
        filtered = _filter_tree(roots, status_filter="error")
        assert _count_spans(filtered) >= 1

    def test_filter_no_match(self):
        roots = self._build_sample_tree()
        filtered = _filter_tree(roots, name_pattern="nonexistent_tool")
        assert filtered == []


class TestFilterContains:
    """Tests for --contains: keep full subtrees containing a matching span."""

    def _build_eval_tree(self):
        spans = _load_jsonl_spans(str(SAMPLE_EVAL_TRACE))
        return _build_tree_from_jsonl(spans)

    def test_contains_unique_span_returns_one_subtree(self):
        roots = self._build_eval_tree()
        # get_random_operator only appears in the first eval run
        filtered = _filter_contains(roots, "get_random_operator")
        assert len(filtered) == 1
        names = _collect_names(filtered)
        assert "get_random_operator" in names
        assert "main" in names
        assert "apply_operator" in names

    def test_contains_common_span_returns_all_subtrees(self):
        roots = self._build_eval_tree()
        # apply_operator appears in both eval runs
        filtered = _filter_contains(roots, "apply_operator")
        # Should return both main subtrees
        assert len(filtered) >= 2
        names = _collect_names(filtered)
        assert "apply_operator" in names

    def test_contains_glob_pattern(self):
        roots = self._build_eval_tree()
        filtered = _filter_contains(roots, "get_random*")
        assert len(filtered) == 1
        names = _collect_names(filtered)
        assert "get_random_operator" in names

    def test_contains_no_match(self):
        roots = self._build_eval_tree()
        filtered = _filter_contains(roots, "nonexistent_function")
        assert filtered == []

    def test_contains_preserves_full_subtree(self):
        roots = self._build_eval_tree()
        filtered = _filter_contains(roots, "get_random_operator")
        # The returned subtree should include siblings of the match
        names = _collect_names(filtered)
        # apply_operator is a sibling of get_random_operator under main
        assert "apply_operator" in names

    def test_contains_cli_integration(self):
        runner = CliRunner()
        result = runner.invoke(
            trace, [str(SAMPLE_EVAL_TRACE), "--contains", "get_random*"]
        )
        assert result.exit_code == 0
        assert "get_random_operator" in result.output
        assert "apply_operator" in result.output

    def test_contains_cli_no_match(self):
        runner = CliRunner()
        result = runner.invoke(
            trace, [str(SAMPLE_EVAL_TRACE), "--contains", "nonexistent"]
        )
        assert result.exit_code == 0
        assert "No spans match" in result.output


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


class TestUtilities:
    def test_parse_otel_time_iso(self):
        dt = _parse_otel_time("2024-01-15T10:30:00.000000Z")
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 15

    def test_parse_otel_time_invalid(self):
        with pytest.raises(ValueError):
            _parse_otel_time("not-a-date")

    def test_safe_parse_json_valid(self):
        assert _safe_parse_json('{"a": 1}') == {"a": 1}

    def test_safe_parse_json_invalid(self):
        assert _safe_parse_json("not json") == "not json"

    def test_safe_parse_json_non_string(self):
        assert _safe_parse_json(42) == 42

    def test_truncate_short(self):
        assert _truncate("hello", 10) == "hello"

    def test_truncate_long(self):
        result = _truncate("a" * 300, 200)
        assert len(result) == 203  # 200 + "..."
        assert result.endswith("...")

    def test_count_spans(self):
        spans = _load_jsonl_spans(str(SAMPLE_TRACE))
        roots = _build_tree_from_jsonl(spans)
        assert _count_spans(roots) == 4


# ---------------------------------------------------------------------------
# CLI integration (click runner)
# ---------------------------------------------------------------------------


class TestTraceCli:
    def test_jsonl_trace(self):
        runner = CliRunner()
        result = runner.invoke(trace, [str(SAMPLE_TRACE)])
        assert result.exit_code == 0
        assert "agent" in result.output
        assert "get_weather" in result.output

    def test_jsonl_trace_full(self):
        runner = CliRunner()
        result = runner.invoke(trace, [str(SAMPLE_TRACE), "--full"])
        assert result.exit_code == 0
        assert "attributes" in result.output

    def test_jsonl_trace_no_input(self):
        runner = CliRunner()
        result = runner.invoke(trace, [str(SAMPLE_TRACE), "--no-input"])
        assert result.exit_code == 0

    def test_jsonl_trace_no_output(self):
        runner = CliRunner()
        result = runner.invoke(trace, [str(SAMPLE_TRACE), "--no-output"])
        assert result.exit_code == 0

    def test_jsonl_filter_by_name(self):
        runner = CliRunner()
        result = runner.invoke(trace, [str(SAMPLE_TRACE), "--name", "get_weather"])
        assert result.exit_code == 0
        assert "get_weather" in result.output

    def test_jsonl_filter_by_span_type(self):
        runner = CliRunner()
        result = runner.invoke(trace, [str(SAMPLE_TRACE), "--span-type", "TOOL"])
        assert result.exit_code == 0
        assert "get_weather" in result.output

    def test_jsonl_filter_no_match(self):
        runner = CliRunner()
        result = runner.invoke(trace, [str(SAMPLE_TRACE), "--name", "nonexistent"])
        assert result.exit_code == 0
        assert "No spans match" in result.output

    def test_eval_json_trace(self):
        runner = CliRunner()
        result = runner.invoke(trace, [str(SAMPLE_EVAL_OUTPUT)])
        assert result.exit_code == 0
        assert "agent" in result.output
        assert "get_weather" in result.output

    def test_eval_json_filter_eval_id(self):
        runner = CliRunner()
        result = runner.invoke(
            trace,
            [str(SAMPLE_EVAL_OUTPUT), "--eval-id", "test-weather-query"],
        )
        assert result.exit_code == 0
        assert "agent" in result.output

    def test_eval_json_missing_eval_id(self):
        runner = CliRunner()
        result = runner.invoke(
            trace, [str(SAMPLE_EVAL_OUTPUT), "--eval-id", "nonexistent"]
        )
        # Should error about no traces found
        assert result.exit_code != 0

    def test_error_trace_shows_errors(self):
        runner = CliRunner()
        result = runner.invoke(trace, [str(SAMPLE_ERROR_TRACE)])
        assert result.exit_code == 0
        assert "✗" in result.output or "error" in result.output.lower()

    def test_file_not_found(self):
        runner = CliRunner()
        result = runner.invoke(trace, ["/nonexistent/path.jsonl"])
        assert result.exit_code != 0

    def test_empty_file(self, tmp_path):
        empty = tmp_path / "empty.jsonl"
        empty.write_text("")
        runner = CliRunner()
        result = runner.invoke(trace, [str(empty)])
        assert result.exit_code != 0

    def test_status_filter(self):
        runner = CliRunner()
        result = runner.invoke(trace, [str(SAMPLE_ERROR_TRACE), "--status", "error"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_names(roots: list[SpanNode]) -> set[str]:
    """Collect all span names in a tree."""
    names: set[str] = set()
    for root in roots:
        names.add(root.name)
        names.update(_collect_names(root.children))
    return names
