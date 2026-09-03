"""Tests for coded run lifecycle telemetry."""

from typing import Any
from unittest.mock import patch

import pytest

from uipath._cli._run_telemetry import RunTelemetry
from uipath.runtime.errors import (
    UiPathErrorCategory,
    UiPathErrorCode,
    UiPathErrorContract,
    UiPathRuntimeError,
)
from uipath.runtime.result import UiPathRuntimeResult, UiPathRuntimeStatus

FOLDER_KEY = "ce7d8971-90ec-4f94-beb5-127d1e05f7b1"
JOB_KEY = "8d1c0b2e-1111-4a2b-9c3d-4e5f60718293"

SCOPE_KEYS = {
    "FolderKey",
    "JobKey",
    "JobId",
    "CloudOrganizationId",
    "CloudTenantId",
    "CloudUserId",
    "ProjectId",
    "ProjectKey",
    "ProcessName",
    "ProcessUuid",
    "ProcessVersion",
    "TraceId",
}


@pytest.fixture(autouse=True)
def cloud_job_env(monkeypatch):
    monkeypatch.setenv("UIPATH_FOLDER_KEY", FOLDER_KEY)
    monkeypatch.setenv("UIPATH_JOB_KEY", JOB_KEY)
    monkeypatch.setenv("UIPATH_JOB_ID", "421")
    monkeypatch.setenv("UIPATH_ORGANIZATION_ID", "org-1")
    monkeypatch.setenv("UIPATH_TENANT_ID", "tenant-1")
    monkeypatch.setenv("UIPATH_PROJECT_ID", "project-1")
    monkeypatch.setenv("PROJECT_KEY", "project-key-1")
    monkeypatch.setenv("UIPATH_PROCESS_KEY", "Invoice Triage Agent")
    monkeypatch.setenv("UIPATH_PROCESS_UUID", "process-1")
    monkeypatch.setenv("UIPATH_PROCESS_VERSION", "1.2.3")
    monkeypatch.setenv("UIPATH_TRACE_ID", "0123456789abcdef0123456789abcdef")
    monkeypatch.setenv("UIPATH_TELEMETRY_ENABLED", "true")


@pytest.fixture
def emitted():
    events: list[tuple[str, dict[str, Any]]] = []

    def record(name: str, properties: dict[str, Any] | None = None) -> None:
        events.append((name, properties or {}))

    with patch("uipath._cli._run_telemetry.track_event", side_effect=record):
        yield events


def start(
    agent_type: str | None = "uipath_coded",
    agent_framework: str | None = "langchain",
    **kwargs: Any,
) -> RunTelemetry | None:
    return RunTelemetry.start(
        agent_type=agent_type,
        agent_framework=agent_framework,
        entrypoint=kwargs.pop("entrypoint", "main"),
        execution_source=kwargs.pop("execution_source", "runtime"),
        is_conversational=kwargs.pop("is_conversational", False),
    )


def started() -> RunTelemetry:
    handle = start()
    assert handle is not None
    return handle


def names(events: list[tuple[str, dict[str, Any]]]) -> list[str]:
    return [name for name, _ in events]


def successful() -> UiPathRuntimeResult:
    return UiPathRuntimeResult(status=UiPathRuntimeStatus.SUCCESSFUL)


class TestClassification:
    def test_python_framework_is_a_function_run(self, emitted):
        start(agent_type="uipath_coded", agent_framework="python")

        assert names(emitted) == ["CodedFunctionRun.Start"]

    def test_non_python_framework_is_a_coded_agent_run(self, emitted):
        start(agent_type="uipath_coded", agent_framework="langchain")

        assert names(emitted) == ["CodedAgentRun.Start"]

    def test_lowcode_is_skipped_because_the_agents_package_emits_its_own(self, emitted):
        handle = start(agent_type="uipath_lowcode", agent_framework="langchain")

        assert handle is None
        assert emitted == []

    def test_factory_without_settings_defaults_to_coded_agent(self, emitted):
        start(agent_type=None, agent_framework=None)

        assert names(emitted) == ["CodedAgentRun.Start"]


class TestScopeBlock:
    def test_scope_is_present_on_start_and_terminal_events(self, emitted):
        started().finished(successful())

        assert len(emitted) == 2
        for name, properties in emitted:
            missing = SCOPE_KEYS - properties.keys()
            assert not missing, f"{name} is missing {sorted(missing)}"

    def test_scope_is_present_on_failed_events(self, emitted):
        started().failed(RuntimeError("boom"))

        _, properties = emitted[-1]
        missing = SCOPE_KEYS - properties.keys()
        assert not missing, f"failed event is missing {sorted(missing)}"

    def test_scope_carries_the_real_values(self, emitted):
        start()

        _, properties = emitted[0]
        assert properties["FolderKey"] == FOLDER_KEY
        assert properties["JobKey"] == JOB_KEY
        assert properties["ProjectKey"] == "project-key-1"
        assert properties["ProjectId"] == "project-1"
        assert properties["ProcessName"] == "Invoice Triage Agent"

    def test_absent_scope_values_are_omitted_not_blank(self, emitted, monkeypatch):
        monkeypatch.delenv("UIPATH_FOLDER_KEY", raising=False)

        start()

        _, properties = emitted[0]
        assert "FolderKey" not in properties


class TestUnauthenticated:
    def test_required_identity_falls_back_to_the_schema_sentinel(
        self, emitted, monkeypatch
    ):
        for var in (
            "UIPATH_ORGANIZATION_ID",
            "UIPATH_TENANT_ID",
            "UIPATH_CLOUD_USER_ID",
            "UIPATH_ACCESS_TOKEN",
        ):
            monkeypatch.delenv(var, raising=False)

        start()

        _, properties = emitted[0]
        assert properties["CloudOrganizationId"] == "N/A"
        assert properties["CloudTenantId"] == "N/A"
        assert properties["CloudUserId"] == "N/A"

    def test_optional_scope_is_still_omitted_when_absent(self, emitted, monkeypatch):
        monkeypatch.delenv("UIPATH_FOLDER_KEY", raising=False)
        monkeypatch.delenv("UIPATH_PROCESS_KEY", raising=False)

        start()

        _, properties = emitted[0]
        assert "FolderKey" not in properties
        assert "ProcessName" not in properties


class TestTerminalStatus:
    def test_successful_result_ends_the_run(self, emitted):
        started().finished(successful())

        name, properties = emitted[-1]
        assert name == "CodedAgentRun.End"
        assert properties["Status"] == "Completed"

    def test_faulted_result_without_an_exception_is_still_a_failure(self, emitted):
        started().finished(
            UiPathRuntimeResult(
                status=UiPathRuntimeStatus.FAULTED,
                error=UiPathErrorContract(
                    code="Python.Boom",
                    title="It broke",
                    detail="stack and user data here",
                    category=UiPathErrorCategory.USER,
                ),
            )
        )

        name, properties = emitted[-1]
        assert name == "CodedAgentRun.Failed"
        assert properties["Status"] == "Failed"
        assert properties["ErrorCode"] == "Python.Boom"
        assert properties["ErrorCategory"] == "User"

    def test_faulted_result_does_not_borrow_the_error_code_as_error_type(self, emitted):
        started().finished(
            UiPathRuntimeResult(
                status=UiPathRuntimeStatus.FAULTED,
                error=UiPathErrorContract(
                    code="Python.Boom",
                    title="It broke",
                    detail="d",
                    category=UiPathErrorCategory.USER,
                ),
            )
        )

        _, properties = emitted[-1]
        assert properties["ErrorCode"] == "Python.Boom"
        assert "ErrorType" not in properties

    def test_faulted_result_without_a_contract_invents_nothing(self, emitted):
        started().finished(UiPathRuntimeResult(status=UiPathRuntimeStatus.FAULTED))

        _, properties = emitted[-1]
        assert properties["Status"] == "Failed"
        assert "ErrorType" not in properties
        assert "ErrorCode" not in properties

    def test_suspended_result_is_waiting_not_failing(self, emitted):
        started().finished(UiPathRuntimeResult(status=UiPathRuntimeStatus.SUSPENDED))

        name, properties = emitted[-1]
        assert name == "CodedAgentRun.End"
        assert properties["Status"] == "Suspended"

    def test_only_terminal_events_carry_a_duration(self, emitted):
        started().finished(successful())

        _, start_props = emitted[0]
        _, end_props = emitted[-1]
        assert "DurationMs" not in start_props
        assert end_props["DurationMs"] >= 0

    def test_duration_is_opt_in_not_inferred_from_the_suffix(self, emitted):
        handle = started()
        handle._emit("Interrupted", {})

        _, properties = emitted[-1]
        assert "DurationMs" not in properties


class TestTraceCorrelation:
    def test_a_dashed_uuid_trace_id_is_normalized_to_hex(self, emitted, monkeypatch):
        monkeypatch.setenv("UIPATH_TRACE_ID", "a1b2c3d4-e5f6-4788-9a0b-1c2d3e4f5a6b")

        start()

        _, properties = emitted[0]
        assert properties["TraceId"] == "a1b2c3d4e5f647889a0b1c2d3e4f5a6b"


class TestRunId:
    def test_a_job_run_is_identified_by_its_job_key(self, emitted):
        started().finished(successful())

        assert {p["AgentRunId"] for _, p in emitted} == {JOB_KEY}

    def test_a_local_run_still_gets_one_shared_id(self, emitted, monkeypatch):
        monkeypatch.delenv("UIPATH_JOB_KEY", raising=False)

        started().finished(successful())

        run_ids = {p["AgentRunId"] for _, p in emitted}
        assert len(run_ids) == 1
        assert run_ids != {JOB_KEY}


class TestRaisedErrors:
    def test_runtime_error_contributes_its_contract(self, emitted):
        started().failed(
            UiPathRuntimeError(
                code=UiPathErrorCode.EXECUTION_ERROR,
                title="Entrypoint blew up",
                detail="secret customer value",
                category=UiPathErrorCategory.USER,
                include_traceback=False,
            )
        )

        name, properties = emitted[-1]
        assert name == "CodedAgentRun.Failed"
        assert properties["ErrorTitle"] == "Entrypoint blew up"
        assert properties["ErrorCategory"] == "User"
        assert properties["ErrorType"] == "UiPathRuntimeError"

    def test_plain_exception_still_reports_a_failure(self, emitted):
        started().failed(ValueError("bad input"))

        name, properties = emitted[-1]
        assert name == "CodedAgentRun.Failed"
        assert properties["Status"] == "Failed"
        assert properties["ErrorType"] == "ValueError"

    def test_customer_content_is_never_shipped(self, emitted):
        started().failed(ValueError("account ACCT-QX7742 balance 99.99"))

        _, properties = emitted[-1]
        assert "ACCT-QX7742" not in repr(properties)
        assert "ErrorMessage" not in properties
        assert "ErrorTraceback" not in properties


class TestSafety:
    def test_disabled_telemetry_emits_nothing(self, emitted, monkeypatch):
        monkeypatch.setenv("UIPATH_TELEMETRY_ENABLED", "false")

        handle = start()

        assert handle is None
        assert emitted == []

    def test_a_broken_backend_does_not_break_the_run(self):
        with patch(
            "uipath._cli._run_telemetry.track_event",
            side_effect=RuntimeError("app insights is down"),
        ):
            handle = start()

            assert handle is not None
            handle.finished(successful())
            handle.failed(ValueError("boom"))
