import json
import os
from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from opentelemetry.sdk.trace import Span as OTelSpan
from opentelemetry.trace import SpanContext, StatusCode

from uipath.platform.common import UiPathSpan, _SpanUtils
from uipath.platform.common._span_utils import (
    ExecutionType,
    SpanSource,
    SpanStatus,
    VerbosityLevel,
)
from uipath.platform.common.constants import (
    ENV_PROJECT_KEY,
    ENV_UIPATH_AGENT_ID,
    ENV_UIPATH_PROJECT_ID,
)


@pytest.fixture(autouse=True)
def _clear_id_cache():
    """Isolate the process-global id cache between tests."""
    from uipath.platform.common._span_utils import _read_config_id

    _read_config_id.cache_clear()
    yield
    _read_config_id.cache_clear()


class TestStrEnums:
    def test_span_status_string_values(self):
        assert SpanStatus.UNSET == "Unset"
        assert SpanStatus.OK == "Ok"
        assert SpanStatus.ERROR == "Error"
        assert SpanStatus.RUNNING == "Running"
        assert SpanStatus.RESTRICTED == "Restricted"
        assert SpanStatus.CANCELLED == "Cancelled"

    def test_span_source_string_values(self):
        assert SpanSource.CODED_AGENTS == "CodedAgents"
        assert SpanSource.AGENTS == "Agents"
        assert SpanSource.PROCESS_ORCHESTRATION == "ProcessOrchestration"
        assert SpanSource.API_WORKFLOWS == "ApiWorkflows"
        assert SpanSource.ROBOTS == "Robots"

    def test_verbosity_level_string_values(self):
        assert VerbosityLevel.VERBOSE == "Verbose"
        assert VerbosityLevel.TRACE == "Trace"
        assert VerbosityLevel.INFORMATION == "Information"
        assert VerbosityLevel.WARNING == "Warning"
        assert VerbosityLevel.ERROR == "Error"
        assert VerbosityLevel.CRITICAL == "Critical"
        assert VerbosityLevel.OFF == "Off"

    def test_execution_type_string_values(self):
        assert ExecutionType.DEBUG == "Debug"
        assert ExecutionType.RUNTIME == "Runtime"

    def test_enums_are_strings(self):
        assert isinstance(SpanStatus.OK, str)
        assert isinstance(SpanSource.CODED_AGENTS, str)
        assert isinstance(VerbosityLevel.INFORMATION, str)
        assert isinstance(ExecutionType.RUNTIME, str)


class TestOTelToUiPathSpan:
    """OTEL attribute -> top-level UiPathSpan field mapping.

    `_SpanUtils.otel_span_to_uipath_span` lifts a small set of OTEL
    span attributes onto dedicated `UiPathSpan` fields surfaced under
    `to_dict()`. This test documents that mapping — adding a new row
    means the attribute is newly mapped, removing one breaks
    downstream consumers.
    """

    ATTRIBUTE_FIELD_MAP = [
        # (otel_attr, span_field, top_level_key, otel_input_int, expected_output)
        ("executionType", "execution_type", "ExecutionType", 1, ExecutionType.RUNTIME),
        ("agentVersion", "agent_version", "AgentVersion", "1.2.3", "1.2.3"),
        ("agentId", "reference_id", "ReferenceId", "ref-abc", "ref-abc"),
        ("verbosityLevel", "verbosity_level", "VerbosityLevel", 6, VerbosityLevel.OFF),
    ]

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_attributes_map_to_top_level_fields(self) -> None:
        attrs = {
            otel_attr: otel_input
            for otel_attr, _, _, otel_input, _ in self.ATTRIBUTE_FIELD_MAP
        }

        mock_span = Mock(spec=OTelSpan)
        mock_context = SpanContext(
            trace_id=0x123456789ABCDEF0123456789ABCDEF0,
            span_id=0x0123456789ABCDEF,
            is_remote=False,
        )
        mock_span.get_span_context.return_value = mock_context
        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = attrs
        mock_span.events = []
        mock_span.links = []
        now_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = now_ns
        mock_span.end_time = now_ns + 1_000_000

        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        span_dict = uipath_span.to_dict()

        for (
            _,
            span_field,
            top_level_key,
            _,
            expected_output,
        ) in self.ATTRIBUTE_FIELD_MAP:
            assert getattr(uipath_span, span_field) == expected_output, span_field
            assert span_dict[top_level_key] == expected_output, top_level_key

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_verbosity_level_omitted_when_unset(self) -> None:
        """Spans that don't set verbosityLevel must not carry the key on the wire.

        Backwards compat: pre-existing spans never emitted VerbosityLevel; the
        LLMOps backend applies its own default. Adding `"VerbosityLevel": null`
        unconditionally would change the wire format for every existing span.
        """
        mock_span = Mock(spec=OTelSpan)
        mock_context = SpanContext(
            trace_id=0x123456789ABCDEF0123456789ABCDEF0,
            span_id=0x0123456789ABCDEF,
            is_remote=False,
        )
        mock_span.get_span_context.return_value = mock_context
        mock_span.name = "legacy-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {"someOtherAttr": "value"}
        mock_span.events = []
        mock_span.links = []
        now_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = now_ns
        mock_span.end_time = now_ns + 1_000_000

        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        span_dict = uipath_span.to_dict()

        assert uipath_span.verbosity_level is None
        assert "VerbosityLevel" not in span_dict


class TestReferenceIdResolution:
    """`reference_id` resolution chain.

    `reference_id` is derived from the span's resolved `agentId` attribute
    (which itself goes through `resolve_project_id()`), falling back to the
    `referenceId` attribute. Falsy values (missing / empty string) at each step
    fall through to the next source. The `referenceId` fallback exists for
    backwards compatibility with older producers that only emit that attribute.
    """

    @pytest.mark.parametrize(
        ("env_value", "attributes", "expected"),
        [
            pytest.param(
                "env-agent",
                {"agentId": "attr-agent", "referenceId": "attr-ref"},
                "env-agent",
                id="env-var-overrides-attr",
            ),
            pytest.param(
                None,
                {"agentId": "attr-agent", "referenceId": "attr-ref"},
                "attr-agent",
                id="agent-id-attr-when-env-unset",
            ),
            pytest.param(
                None,
                {"referenceId": "attr-ref"},
                "attr-ref",
                id="reference-id-fallback-when-agent-id-missing",
            ),
            pytest.param(
                None,
                {"agentId": "", "referenceId": "attr-ref"},
                "attr-ref",
                id="reference-id-fallback-when-agent-id-empty",
            ),
            pytest.param(
                None,
                {},
                None,
                id="none-when-all-sources-missing",
            ),
        ],
    )
    def test_reference_id_chain(
        self,
        env_value: str | None,
        attributes: dict[str, object],
        expected: str | None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from uipath.platform.common._span_utils import _read_config_id

        _read_config_id.cache_clear()
        monkeypatch.delenv(ENV_UIPATH_AGENT_ID, raising=False)
        monkeypatch.delenv(ENV_UIPATH_PROJECT_ID, raising=False)
        if env_value is None:
            monkeypatch.delenv(ENV_PROJECT_KEY, raising=False)
        else:
            monkeypatch.setenv(ENV_PROJECT_KEY, env_value)

        mock_span = Mock(spec=OTelSpan)
        mock_context = SpanContext(
            trace_id=0x123456789ABCDEF0123456789ABCDEF0,
            span_id=0x0123456789ABCDEF,
            is_remote=False,
        )
        mock_span.get_span_context.return_value = mock_context
        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = attributes
        mock_span.events = []
        mock_span.links = []
        now_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = now_ns
        mock_span.end_time = now_ns + 1_000_000

        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        assert uipath_span.reference_id == expected


class TestAgentIdResolution:
    """`agentId` span attribute resolution via `resolve_project_id()`.

    Priority: `uipath.json#id` (cached, read once per process) > `UIPATH_AGENT_ID`
    / `UIPATH_PROJECT_ID` > the legacy `PROJECT_KEY` env var injected by the
    executor at runtime. When no source is present the `agentId` attribute is
    omitted entirely.
    """

    @staticmethod
    def _make_span() -> Mock:
        mock_span = Mock(spec=OTelSpan)
        mock_context = SpanContext(
            trace_id=0x123456789ABCDEF0123456789ABCDEF0,
            span_id=0x0123456789ABCDEF,
            is_remote=False,
        )
        mock_span.get_span_context.return_value = mock_context
        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {}
        mock_span.events = []
        mock_span.links = []
        now_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = now_ns
        mock_span.end_time = now_ns + 1_000_000
        return mock_span

    @staticmethod
    def _resolve(monkeypatch: pytest.MonkeyPatch, tmp_path) -> object:
        from uipath.platform.common._span_utils import _read_config_id

        _read_config_id.cache_clear()
        monkeypatch.delenv("UIPATH_CONFIG_PATH", raising=False)
        monkeypatch.delenv(ENV_UIPATH_AGENT_ID, raising=False)
        monkeypatch.delenv(ENV_UIPATH_PROJECT_ID, raising=False)
        monkeypatch.chdir(tmp_path)
        uipath_span = _SpanUtils.otel_span_to_uipath_span(
            TestAgentIdResolution._make_span(), serialize_attributes=False
        )
        attributes = uipath_span.attributes
        assert isinstance(attributes, dict)
        return attributes.get("agentId")

    def test_agent_id_from_uipath_json_wins_over_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        (tmp_path / "uipath.json").write_text(
            json.dumps({"id": "00000000-0000-0000-0000-000000000001"})
        )
        monkeypatch.setenv(ENV_PROJECT_KEY, "from-env")
        assert (
            self._resolve(monkeypatch, tmp_path)
            == "00000000-0000-0000-0000-000000000001"
        )

    def test_agent_id_falls_back_to_project_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        # No uipath.json on disk.
        monkeypatch.setenv(ENV_PROJECT_KEY, "from-env")
        assert self._resolve(monkeypatch, tmp_path) == "from-env"

    def test_agent_id_falls_back_when_config_has_no_id(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        (tmp_path / "uipath.json").write_text(json.dumps({"functions": {}}))
        monkeypatch.setenv(ENV_PROJECT_KEY, "from-env")
        assert self._resolve(monkeypatch, tmp_path) == "from-env"

    def test_agent_id_absent_when_no_source(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.delenv(ENV_PROJECT_KEY, raising=False)
        assert self._resolve(monkeypatch, tmp_path) is None

    def test_non_guid_config_id_is_ignored_and_falls_back(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        # A malformed (non-GUID) id must not reach ReferenceId; fall back to env.
        (tmp_path / "uipath.json").write_text(json.dumps({"id": "not-a-guid"}))
        monkeypatch.setenv(ENV_PROJECT_KEY, "from-env")
        assert self._resolve(monkeypatch, tmp_path) == "from-env"

    def test_config_id_is_cached(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        from uipath.platform.common._span_utils import _read_config_id

        first = "00000000-0000-0000-0000-000000000001"
        second = "00000000-0000-0000-0000-000000000002"

        _read_config_id.cache_clear()
        monkeypatch.delenv("UIPATH_CONFIG_PATH", raising=False)
        monkeypatch.chdir(tmp_path)
        config = tmp_path / "uipath.json"

        config.write_text(json.dumps({"id": first}))
        assert _read_config_id() == first

        # A later edit is not observed: the value is read once and cached.
        config.write_text(json.dumps({"id": second}))
        assert _read_config_id() == first

        _read_config_id.cache_clear()
        assert _read_config_id() == second


class TestNormalizeIds:
    """Tests for OTEL ID normalization functions."""

    def test_normalize_trace_id_from_hex(self):
        """Test normalizing a 32-char hex trace ID."""
        trace_id = "1234567890abcdef1234567890abcdef"
        result = _SpanUtils.normalize_trace_id(trace_id)
        assert result == "1234567890abcdef1234567890abcdef"

    def test_normalize_trace_id_from_uuid(self):
        """Test normalizing a UUID format trace ID to hex."""
        trace_id = "12345678-90ab-cdef-1234-567890abcdef"
        result = _SpanUtils.normalize_trace_id(trace_id)
        assert result == "1234567890abcdef1234567890abcdef"

    def test_normalize_trace_id_uppercase(self):
        """Test normalizing uppercase hex to lowercase."""
        trace_id = "1234567890ABCDEF1234567890ABCDEF"
        result = _SpanUtils.normalize_trace_id(trace_id)
        assert result == "1234567890abcdef1234567890abcdef"

    def test_normalize_trace_id_invalid_length(self):
        """Test that invalid length raises ValueError."""
        with pytest.raises(ValueError, match="Invalid trace ID format"):
            _SpanUtils.normalize_trace_id("1234")

    def test_normalize_span_id_from_hex(self):
        """Test normalizing a 16-char hex span ID."""
        span_id = "1234567890abcdef"
        result = _SpanUtils.normalize_span_id(span_id)
        assert result == "1234567890abcdef"

    def test_normalize_span_id_from_uuid(self):
        """Test normalizing a UUID format span ID (takes last 16 chars)."""
        span_id = "00000000-0000-0000-1234-567890abcdef"
        result = _SpanUtils.normalize_span_id(span_id)
        assert result == "1234567890abcdef"

    def test_normalize_span_id_uppercase(self):
        """Test normalizing uppercase hex to lowercase."""
        span_id = "1234567890ABCDEF"
        result = _SpanUtils.normalize_span_id(span_id)
        assert result == "1234567890abcdef"

    def test_normalize_span_id_invalid_length(self):
        """Test that invalid length raises ValueError."""
        with pytest.raises(ValueError, match="Invalid span ID format"):
            _SpanUtils.normalize_span_id("1234")


class TestSpanUtils:
    @patch.dict(
        os.environ,
        {
            "UIPATH_ORGANIZATION_ID": "test-org",
            "UIPATH_TENANT_ID": "test-tenant",
            "UIPATH_FOLDER_KEY": "test-folder",
            "UIPATH_PROCESS_UUID": "test-process",
            "UIPATH_JOB_KEY": "test-job",
        },
    )
    def test_otel_span_to_uipath_span(self):
        # Create a mock OTel span
        mock_span = Mock(spec=OTelSpan)

        # Set span context
        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        # Set span properties
        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {
            "key1": "value1",
            "key2": 123,
            "span_type": "CustomSpanType",
        }
        mock_span.events = []
        mock_span.links = []

        # Set times
        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000  # 1ms later

        # Convert to UiPath span
        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)

        # Verify the conversion
        assert isinstance(uipath_span, UiPathSpan)
        assert uipath_span.name == "test-span"
        assert uipath_span.status == SpanStatus.OK
        assert uipath_span.span_type == "CustomSpanType"

        # Verify IDs are in OTEL hex format
        assert uipath_span.trace_id == "123456789abcdef0123456789abcdef0"  # 32-char hex
        assert uipath_span.id == "0123456789abcdef"  # 16-char hex
        assert uipath_span.parent_id is None

        # Verify attributes
        attributes_value = uipath_span.attributes
        attributes = (
            json.loads(attributes_value)
            if isinstance(attributes_value, str)
            else attributes_value
        )
        assert attributes["key1"] == "value1"
        assert attributes["key2"] == 123

        # Test with error status
        mock_span.status.description = "Test error description"
        mock_span.status.status_code = StatusCode.ERROR
        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        assert uipath_span.status == SpanStatus.ERROR

    @patch.dict(
        os.environ,
        {
            "UIPATH_ORGANIZATION_ID": "test-org",
            "UIPATH_TENANT_ID": "test-tenant",
        },
    )
    def test_otel_span_to_uipath_span_optimized_path(self):
        """Test the optimized path where attributes are kept as dict."""
        # Create a mock OTel span
        mock_span = Mock(spec=OTelSpan)

        # Set span context
        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        # Set span properties
        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {
            "key1": "value1",
            "key2": 123,
        }
        mock_span.events = []
        mock_span.links = []

        # Set times
        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000

        # Test optimized path: serialize_attributes=False
        uipath_span = _SpanUtils.otel_span_to_uipath_span(
            mock_span, serialize_attributes=False
        )

        # Verify attributes is a dict (not JSON string)
        assert isinstance(uipath_span.attributes, dict)
        assert uipath_span.attributes["key1"] == "value1"
        assert uipath_span.attributes["key2"] == 123

        # Test to_dict with serialize_attributes=False
        span_dict = uipath_span.to_dict(serialize_attributes=False)
        assert isinstance(span_dict["Attributes"], dict)
        assert span_dict["Attributes"]["key1"] == "value1"

        # Test to_dict with serialize_attributes=True
        span_dict_serialized = uipath_span.to_dict(serialize_attributes=True)
        assert isinstance(span_dict_serialized["Attributes"], str)
        attrs = json.loads(span_dict_serialized["Attributes"])
        assert attrs["key1"] == "value1"
        assert attrs["key2"] == 123

    @patch.dict(os.environ, {"UIPATH_TRACE_ID": "00000000-0000-4000-8000-000000000000"})
    def test_otel_span_to_uipath_span_with_env_trace_id_uuid_format(self):
        """Test that UUID format UIPATH_TRACE_ID is normalized to hex."""
        # Create a mock OTel span
        mock_span = Mock(spec=OTelSpan)

        # Set span context
        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            is_remote=False,
        )
        mock_span.get_span_context.return_value = mock_context

        # Set span properties
        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {}
        mock_span.events = []
        mock_span.links = []

        # Set times
        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000  # 1ms later

        # Convert to UiPath span
        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)

        # Verify the trace ID is normalized to 32-char hex format
        assert uipath_span.trace_id == "00000000000040008000000000000000"

    @patch.dict(os.environ, {"UIPATH_TRACE_ID": "1234567890abcdef1234567890abcdef"})
    def test_otel_span_to_uipath_span_with_env_trace_id_hex_format(self):
        """Test that hex format UIPATH_TRACE_ID is used directly."""
        # Create a mock OTel span
        mock_span = Mock(spec=OTelSpan)

        # Set span context
        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            is_remote=False,
        )
        mock_span.get_span_context.return_value = mock_context

        # Set span properties
        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {}
        mock_span.events = []
        mock_span.links = []

        # Set times
        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000  # 1ms later

        # Convert to UiPath span
        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)

        # Verify the trace ID is used as-is (lowercase)
        assert uipath_span.trace_id == "1234567890abcdef1234567890abcdef"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_uipath_span_includes_execution_type(self):
        """Test that executionType from attributes becomes top-level ExecutionType."""
        mock_span = Mock(spec=OTelSpan)

        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {"executionType": 0}
        mock_span.events = []
        mock_span.links = []

        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000

        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        span_dict = uipath_span.to_dict()

        assert span_dict["ExecutionType"] == ExecutionType.DEBUG
        assert uipath_span.execution_type == ExecutionType.DEBUG

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_uipath_span_includes_agent_version(self):
        """Test that agentVersion from attributes becomes top-level AgentVersion."""
        mock_span = Mock(spec=OTelSpan)

        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {"agentVersion": "2.0.0"}
        mock_span.events = []
        mock_span.links = []

        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000

        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        span_dict = uipath_span.to_dict()

        assert span_dict["AgentVersion"] == "2.0.0"
        assert uipath_span.agent_version == "2.0.0"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_uipath_span_execution_type_and_agent_version_both(self):
        """Test that both executionType and agentVersion are extracted together."""
        mock_span = Mock(spec=OTelSpan)

        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        mock_span.name = "Agent run - Agent"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {"executionType": 1, "agentVersion": "1.0.0"}
        mock_span.events = []
        mock_span.links = []

        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000

        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        span_dict = uipath_span.to_dict()

        assert span_dict["ExecutionType"] == ExecutionType.RUNTIME
        assert span_dict["AgentVersion"] == "1.0.0"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_uipath_span_missing_execution_type_and_agent_version(self):
        """Test that missing executionType and agentVersion default to None."""
        mock_span = Mock(spec=OTelSpan)

        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        mock_span.attributes = {"someOtherAttr": "value"}
        mock_span.events = []
        mock_span.links = []

        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000

        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        span_dict = uipath_span.to_dict()

        assert span_dict["ExecutionType"] is None
        assert span_dict["AgentVersion"] is None

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_uipath_span_source_defaults_to_coded_agents(self):
        """Test that Source defaults to CodedAgents and ignores attributes.source."""
        mock_span = Mock(spec=OTelSpan)

        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        # source in attributes should NOT override top-level Source
        mock_span.attributes = {"source": "runtime"}
        mock_span.events = []
        mock_span.links = []

        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000

        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        span_dict = uipath_span.to_dict()

        # Top-level Source should be CodedAgents, string "runtime" is ignored
        assert uipath_span.source == SpanSource.CODED_AGENTS
        assert span_dict["Source"] == "CodedAgents"

        # attributes.source string should still be in Attributes JSON
        attrs = json.loads(span_dict["Attributes"])
        assert attrs["source"] == "runtime"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_uipath_span_source_override_with_uipath_source(self):
        """Test that uipath.source attribute overrides default (for low-code agents)."""
        mock_span = Mock(spec=OTelSpan)

        trace_id = 0x123456789ABCDEF0123456789ABCDEF0
        span_id = 0x0123456789ABCDEF
        mock_context = SpanContext(trace_id=trace_id, span_id=span_id, is_remote=False)
        mock_span.get_span_context.return_value = mock_context

        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = StatusCode.OK
        # uipath.source=1 (Agents) overrides default of 10 (CodedAgents)
        mock_span.attributes = {"uipath.source": 1, "source": "runtime"}
        mock_span.events = []
        mock_span.links = []

        current_time_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = current_time_ns
        mock_span.end_time = current_time_ns + 1000000

        uipath_span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        span_dict = uipath_span.to_dict()

        # uipath.source overrides - low-code agents use 1 (Agents)
        assert uipath_span.source == SpanSource.AGENTS
        assert span_dict["Source"] == "Agents"

        # String source still in Attributes JSON
        attrs = json.loads(span_dict["Attributes"])
        assert attrs["source"] == "runtime"


class TestUiPathSpanDictUsesStrings:
    def test_default_status_is_ok_string(self):
        span = UiPathSpan(
            id="a" * 16,
            trace_id="b" * 32,
            name="test",
            attributes={},
        )
        d = span.to_dict()
        assert d["Status"] == "Ok"

    def test_default_source_is_coded_agents_string(self):
        span = UiPathSpan(
            id="a" * 16,
            trace_id="b" * 32,
            name="test",
            attributes={},
        )
        d = span.to_dict()
        assert d["Source"] == "CodedAgents"

    def test_verbosity_level_serializes_as_string(self):
        span = UiPathSpan(
            id="a" * 16,
            trace_id="b" * 32,
            name="test",
            attributes={},
            verbosity_level=VerbosityLevel.OFF,
        )
        d = span.to_dict()
        assert d["VerbosityLevel"] == "Off"

    def test_execution_type_serializes_as_string(self):
        span = UiPathSpan(
            id="a" * 16,
            trace_id="b" * 32,
            name="test",
            attributes={},
            execution_type=ExecutionType.RUNTIME,
        )
        d = span.to_dict()
        assert d["ExecutionType"] == "Runtime"


class TestOtelSpanConversionUsesStrEnums:
    def _make_mock_span(self, status_code=StatusCode.OK, attributes=None):
        from datetime import datetime
        from unittest.mock import Mock

        from opentelemetry.trace import SpanContext

        mock_span = Mock()
        mock_context = SpanContext(
            trace_id=0x123456789ABCDEF0123456789ABCDEF0,
            span_id=0x0123456789ABCDEF,
            is_remote=False,
        )
        mock_span.get_span_context.return_value = mock_context
        mock_span.name = "test-span"
        mock_span.parent = None
        mock_span.status.status_code = status_code
        mock_span.status.description = None
        mock_span.attributes = attributes or {}
        mock_span.events = []
        mock_span.links = []
        now_ns = int(datetime.now().timestamp() * 1e9)
        mock_span.start_time = now_ns
        mock_span.end_time = now_ns + 1_000_000
        return mock_span

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_ok_status_maps_to_str_enum(self):
        span = _SpanUtils.otel_span_to_uipath_span(self._make_mock_span())
        assert span.status == SpanStatus.OK
        assert span.to_dict()["Status"] == "Ok"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_error_status_maps_to_str_enum(self):
        mock_span = self._make_mock_span(status_code=StatusCode.ERROR)
        mock_span.status.description = "something went wrong"
        span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        assert span.status == SpanStatus.ERROR
        assert span.to_dict()["Status"] == "Error"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_default_source_is_coded_agents(self):
        span = _SpanUtils.otel_span_to_uipath_span(self._make_mock_span())
        assert span.source == SpanSource.CODED_AGENTS
        assert span.to_dict()["Source"] == "CodedAgents"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_execution_type_int_maps_to_str_enum(self):
        mock_span = self._make_mock_span(attributes={"executionType": 1})
        span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        assert span.execution_type == ExecutionType.RUNTIME
        assert span.to_dict()["ExecutionType"] == "Runtime"

    @patch.dict(os.environ, {"UIPATH_ORGANIZATION_ID": "test-org"})
    def test_verbosity_level_int_maps_to_str_enum(self):
        mock_span = self._make_mock_span(attributes={"verbosityLevel": 6})
        span = _SpanUtils.otel_span_to_uipath_span(mock_span)
        assert span.verbosity_level == VerbosityLevel.OFF
        assert span.to_dict()["VerbosityLevel"] == "Off"
