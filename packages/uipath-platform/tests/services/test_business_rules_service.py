import json
from typing import Any, Iterator
from unittest.mock import AsyncMock, Mock

import pytest
from opentelemetry import trace
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags
from pydantic import ValidationError
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.business_rules import (
    BusinessRulesService,
    BusinessRuleStatus,
    DebugRunContext,
    DeployedRunContext,
    RunMode,
    TraceContext,
)
from uipath.platform.constants import HEADER_FOLDER_KEY, HEADER_USER_AGENT
from uipath.platform.errors import EnrichedException

FOLDER_KEY = "5f1f1b0e-2b8a-4c1e-9b8e-1a2b3c4d5e6f"
TRACEPARENT = "x-uipath-traceparent-id"
JOB_KEY = "9d8c7b6a-5f4e-3d2c-1b0a-9f8e7d6c5b4a"
LOAN_PRICING = DeployedRunContext(rule_name="Loan Pricing")


@pytest.fixture
def folders_service() -> Mock:
    folders = Mock()
    folders.retrieve_folder_key.return_value = FOLDER_KEY
    folders.retrieve_folder_key_async = AsyncMock(return_value=FOLDER_KEY)
    return folders


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    folders_service: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> BusinessRulesService:
    monkeypatch.delenv("UIPATH_FOLDER_KEY", raising=False)
    monkeypatch.delenv("UIPATH_FOLDER_PATH", raising=False)
    monkeypatch.delenv("UIPATH_JOB_KEY", raising=False)
    return BusinessRulesService(
        config=config,
        execution_context=execution_context,
        folders_service=folders_service,
    )


@pytest.fixture
def evaluate_url(base_url: str, org: str, tenant: str) -> str:
    return f"{base_url}{org}{tenant}/businessrules_/v1/business-rules/evaluate"


@pytest.fixture
def debug_url(base_url: str, org: str, tenant: str) -> str:
    return f"{base_url}{org}{tenant}/businessrules_/v1/business-rules/debug/evaluate"


def _response(results: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {
        "hasPartialSuccess": False,
        "stats": {"submitted": 1, "succeeded": 1, "failed": 0, "notEvaluated": 0},
        "results": results,
        "meta": {"timestamp": "2026-09-28T00:00:00Z"},
        **extra,
    }


def _one_decision(**outputs: Any) -> list[dict[str, Any]]:
    return [
        {
            "id": "input-1",
            "decisions": [{"decisionName": "RiskGrade", "outputs": outputs}],
        }
    ]


class TestRunContext:
    def test_requires_a_run_context(self, service: BusinessRulesService) -> None:
        with pytest.raises(ValueError, match="neither was"):
            service.run({}, folder_key=FOLDER_KEY)

    def test_rejects_both_run_contexts(self, service: BusinessRulesService) -> None:
        debug = DebugRunContext(project_id="proj-1")

        with pytest.raises(ValueError, match="both were"):
            service.run({}, deployed=LOAN_PRICING, debug=debug, folder_key=FOLDER_KEY)

    @pytest.mark.parametrize(
        "rule_name",
        ["", "   ", "a/b", "a\\b", "a..b", "a%20b", "a\nb", "x" * 257],
    )
    def test_rejects_unsafe_rule_names(
        self, service: BusinessRulesService, rule_name: str
    ) -> None:
        deployed = DeployedRunContext(rule_name=rule_name)

        with pytest.raises(ValueError, match="deployed.rule_name"):
            service.run({}, deployed=deployed, folder_key=FOLDER_KEY)

    def test_rejects_oversized_input(self, service: BusinessRulesService) -> None:
        with pytest.raises(ValueError, match="256 keys"):
            service.run(
                {f"k{i}": i for i in range(257)},
                deployed=LOAN_PRICING,
                folder_key=FOLDER_KEY,
            )


class TestFolder:
    def test_resolves_folder_path_to_key(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        folders_service: Mock,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response([]))

        service.run({}, deployed=LOAN_PRICING, folder_path="Finance/Loans")

        folders_service.retrieve_folder_key.assert_called_once_with("Finance/Loans")
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY
        assert "x-uipath-folderpath" not in request.headers

    def test_falls_back_to_env_folder_key(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: Mock,
        evaluate_url: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("UIPATH_FOLDER_KEY", "env-folder-key")
        service = BusinessRulesService(config, execution_context, folders_service)
        httpx_mock.add_response(url=evaluate_url, json=_response([]))

        service.run({}, deployed=LOAN_PRICING)

        folders_service.retrieve_folder_key.assert_not_called()
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == "env-folder-key"

    def test_falls_back_to_env_folder_path(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: Mock,
        evaluate_url: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("UIPATH_FOLDER_PATH", "Finance/Loans")
        service = BusinessRulesService(config, execution_context, folders_service)
        httpx_mock.add_response(url=evaluate_url, json=_response([]))

        service.run({}, deployed=LOAN_PRICING)

        folders_service.retrieve_folder_key.assert_called_once_with("Finance/Loans")
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY
        assert "x-uipath-folderpath" not in request.headers

    async def test_falls_back_to_env_folder_path_async(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: Mock,
        evaluate_url: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("UIPATH_FOLDER_PATH", "Finance/Loans")
        service = BusinessRulesService(config, execution_context, folders_service)
        httpx_mock.add_response(url=evaluate_url, json=_response([]))

        await service.run_async({}, deployed=LOAN_PRICING)

        folders_service.retrieve_folder_key_async.assert_awaited_once_with(
            "Finance/Loans"
        )
        folders_service.retrieve_folder_key.assert_not_called()
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY

    def test_env_folder_key_wins_over_env_folder_path(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: Mock,
        evaluate_url: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("UIPATH_FOLDER_KEY", "env-folder-key")
        monkeypatch.setenv("UIPATH_FOLDER_PATH", "Finance/Loans")
        service = BusinessRulesService(config, execution_context, folders_service)
        httpx_mock.add_response(url=evaluate_url, json=_response([]))

        service.run({}, deployed=LOAN_PRICING)

        folders_service.retrieve_folder_key.assert_not_called()
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == "env-folder-key"

    def test_deployed_requires_a_folder(self, service: BusinessRulesService) -> None:
        with pytest.raises(ValueError, match="deployed business rule"):
            service.run({}, deployed=LOAN_PRICING)

    def test_rejects_both_folder_key_and_path(
        self, service: BusinessRulesService
    ) -> None:
        with pytest.raises(ValueError, match="Only one of"):
            service.run(
                {},
                deployed=LOAN_PRICING,
                folder_key=FOLDER_KEY,
                folder_path="Finance",
            )


class TestDeployed:
    def test_sends_single_input_and_maps_decisions(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=evaluate_url,
            method="POST",
            json=_response(
                _one_decision(Grade="B", Rate=3.5),
                businessRuleName="Loan Pricing",
                version="1.0.3",
            ),
        )

        result = service.run(
            {"creditScore": 740},
            deployed=DeployedRunContext(rule_name="Loan Pricing", version="1.0.3"),
            decision_names=["RiskGrade"],
            explain=True,
            folder_key=FOLDER_KEY,
        )

        assert result.mode == RunMode.DEPLOYED
        assert result.status == BusinessRuleStatus.SUCCESS
        assert result.decisions[0].decision_name == "RiskGrade"
        assert result.decisions[0].outputs == {"Grade": "B", "Rate": 3.5}
        assert result.errors == []
        assert result.top_level_error is None
        assert result.business_rule_name == "Loan Pricing"
        assert result.version == "1.0.3"
        assert result.project_id is None

        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.content) == {
            "businessRuleName": "Loan Pricing",
            "version": "1.0.3",
            "decisionNames": ["RiskGrade"],
            "explain": True,
            "inputs": [{"id": "input-1", "data": {"creditScore": 740}}],
        }
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY
        assert request.headers["Authorization"] == "Bearer secret"
        assert (
            request.headers[HEADER_USER_AGENT]
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.BusinessRulesService.run/{version}"
        )

    def test_omits_optional_fields(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response([]))

        service.run({}, deployed=LOAN_PRICING, folder_key=FOLDER_KEY)

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert "version" not in body
        assert "decisionNames" not in body
        assert body["explain"] is False

    async def test_run_async_resolves_folder_path(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        folders_service: Mock,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response(_one_decision(x=1)))

        result = await service.run_async(
            {"a": 1}, deployed=LOAN_PRICING, folder_path="Finance"
        )

        folders_service.retrieve_folder_key_async.assert_awaited_once_with("Finance")
        assert result.mode == RunMode.DEPLOYED
        assert result.status == BusinessRuleStatus.SUCCESS
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY


class TestDebug:
    def test_by_project_id(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        debug_url: str,
    ) -> None:
        httpx_mock.add_response(
            url=debug_url,
            method="POST",
            json=_response(
                _one_decision(x=1),
                projectId="proj-1",
                fileName="Rules/Loan.dmn",
                traceId="abc123",
            ),
        )

        result = service.run(
            {"a": 1},
            debug=DebugRunContext(project_id="proj-1", file_name="loan.dmn"),
        )

        assert result.mode == RunMode.DEBUG
        assert result.status == BusinessRuleStatus.SUCCESS
        assert result.project_id == "proj-1"
        assert result.file_name == "Rules/Loan.dmn"
        assert result.business_rule_name is None

        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.content) == {
            "projectId": "proj-1",
            "fileName": "loan.dmn",
            "explain": False,
            "inputs": [{"id": "input-1", "data": {"a": 1}}],
        }
        assert "x-uipath-jobkey" not in request.headers
        assert "x-uipath-organizationunitid" not in request.headers
        assert HEADER_FOLDER_KEY not in request.headers

    def test_by_rule_name_sends_job_and_folder_headers(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        debug_url: str,
    ) -> None:
        httpx_mock.add_response(url=debug_url, json=_response([]))

        service.run(
            {},
            debug=DebugRunContext(
                rule_name="Loan Pricing", job_key=JOB_KEY, organization_unit_id=42
            ),
            folder_key=FOLDER_KEY,
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.content)["businessRuleName"] == "Loan Pricing"
        assert request.headers["x-uipath-jobkey"] == JOB_KEY
        assert request.headers["x-uipath-organizationunitid"] == "42"
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY

    def test_job_key_defaults_from_env(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        debug_url: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("UIPATH_JOB_KEY", JOB_KEY)
        httpx_mock.add_response(url=debug_url, json=_response([]))

        service.run(
            {},
            debug=DebugRunContext(rule_name="Loan Pricing", organization_unit_id=42),
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["x-uipath-jobkey"] == JOB_KEY

    def test_explain_requires_a_folder(self, service: BusinessRulesService) -> None:
        debug = DebugRunContext(project_id="proj-1")

        with pytest.raises(ValueError, match="explain=True"):
            service.run({}, debug=debug, explain=True)

    def test_explain_sends_resolved_folder_key(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        folders_service: Mock,
        debug_url: str,
    ) -> None:
        httpx_mock.add_response(url=debug_url, json=_response([]))

        service.run(
            {},
            debug=DebugRunContext(project_id="proj-1"),
            explain=True,
            folder_path="Finance",
        )

        folders_service.retrieve_folder_key.assert_called_once_with("Finance")
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY

    def test_requires_project_or_rule_name(self, service: BusinessRulesService) -> None:
        debug = DebugRunContext(file_name="loan.dmn")

        with pytest.raises(ValueError, match="project_id or debug.rule_name"):
            service.run({}, debug=debug)

    def test_rule_name_requires_job_key(self, service: BusinessRulesService) -> None:
        debug = DebugRunContext(rule_name="Loan Pricing", organization_unit_id=42)

        with pytest.raises(ValueError, match="job_key"):
            service.run({}, debug=debug)

    def test_accepts_organization_unit_id_as_numeric_string(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        debug_url: str,
    ) -> None:
        httpx_mock.add_response(url=debug_url, json=_response([]))

        debug = DebugRunContext.model_validate(
            {
                "rule_name": "Loan Pricing",
                "job_key": JOB_KEY,
                "organization_unit_id": "42",
            }
        )
        assert debug.organization_unit_id == 42

        service.run({}, debug=debug)

        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["x-uipath-organizationunitid"] == "42"

    def test_project_id_with_rule_name_needs_no_job_or_folder_id(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        debug_url: str,
    ) -> None:
        # The service uses a named project as given; the job lineage is never read.
        httpx_mock.add_response(url=debug_url, json=_response([]))

        service.run(
            {},
            debug=DebugRunContext(project_id="proj-1", rule_name="Loan Pricing"),
        )

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body["projectId"] == "proj-1"
        assert body["businessRuleName"] == "Loan Pricing"
        assert "x-uipath-jobkey" not in request.headers
        assert "x-uipath-organizationunitid" not in request.headers

    def test_rule_name_requires_organization_unit(
        self, service: BusinessRulesService
    ) -> None:
        debug = DebugRunContext(rule_name="Loan Pricing", job_key=JOB_KEY)

        with pytest.raises(ValueError, match="organization_unit_id"):
            service.run({}, debug=debug)

    def test_rejects_unsafe_debug_rule_name(
        self, service: BusinessRulesService
    ) -> None:
        debug = DebugRunContext(rule_name="a/b", job_key=JOB_KEY)

        with pytest.raises(ValueError, match="debug.rule_name"):
            service.run({}, debug=debug)

    async def test_run_async_debug(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        debug_url: str,
    ) -> None:
        httpx_mock.add_response(url=debug_url, json=_response([], projectId="proj-1"))

        result = await service.run_async({}, debug=DebugRunContext(project_id="proj-1"))

        assert result.mode == RunMode.DEBUG
        assert result.project_id == "proj-1"
        assert result.status == BusinessRuleStatus.ALL_FAILED


class TestResult:
    def test_partial_success_on_207(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(
            url=evaluate_url,
            status_code=207,
            json=_response(
                [
                    {
                        "id": "input-1",
                        "decisions": [
                            {"decisionName": "RiskGrade", "outputs": {"Grade": "B"}},
                            {
                                "decisionName": "Payment",
                                "error": {
                                    "code": "DECISION_FAILED",
                                    "message": "null arithmetic",
                                },
                            },
                        ],
                    }
                ]
            ),
        )

        result = service.run({}, deployed=LOAN_PRICING, folder_key=FOLDER_KEY)

        assert result.status == BusinessRuleStatus.PARTIAL_SUCCESS
        assert result.decisions[1].error is not None
        assert result.decisions[1].error.code == "DECISION_FAILED"

    def test_input_level_error_is_all_failed(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(
            url=evaluate_url,
            status_code=207,
            json=_response(
                [
                    {
                        "id": "input-1",
                        "errors": [
                            {
                                "code": "INPUT_VALIDATION_FAILED",
                                "message": "creditScore must be a number",
                            }
                        ],
                    }
                ]
            ),
        )

        result = service.run({}, deployed=LOAN_PRICING, folder_key=FOLDER_KEY)

        assert result.status == BusinessRuleStatus.ALL_FAILED
        assert result.errors[0].code == "INPUT_VALIDATION_FAILED"

    def test_not_evaluated_carries_top_level_error(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(
            url=evaluate_url,
            status_code=207,
            json=_response(
                [],
                notEvaluatedIds=["input-1"],
                error={"code": "BATCH_TIMEOUT", "message": "ran out of time"},
            ),
        )

        result = service.run({}, deployed=LOAN_PRICING, folder_key=FOLDER_KEY)

        assert result.status == BusinessRuleStatus.ALL_FAILED
        assert result.decisions == []
        assert result.top_level_error == "BATCH_TIMEOUT"

    def test_raises_enriched_exception_on_error_envelope(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(
            url=evaluate_url,
            status_code=404,
            json={
                "businessRuleName": "Missing",
                "error": {"code": "RULE_NOT_FOUND", "message": "no such rule"},
                "meta": {"timestamp": "2026-09-28T00:00:00Z"},
            },
        )

        deployed = DeployedRunContext(rule_name="Missing")

        with pytest.raises(EnrichedException) as exc:
            service.run({}, deployed=deployed, folder_key=FOLDER_KEY)

        assert exc.value.status_code == 404


EXPLICIT_TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
EXPLICIT_SPAN_ID = "00f067aa0ba902b7"
AMBIENT_TRACE_ID = "0af7651916cd43dd8448eb211c80319c"
AMBIENT_SPAN_ID = "b7ad6b7169203331"


@pytest.fixture
def ambient_span() -> Iterator[None]:
    span = NonRecordingSpan(
        SpanContext(
            trace_id=int(AMBIENT_TRACE_ID, 16),
            span_id=int(AMBIENT_SPAN_ID, 16),
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
    )
    with trace.use_span(span):
        yield


class TestTraceContext:
    def test_explicit_trace_context_wins_over_ambient_span(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
        ambient_span: None,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response([]))
        explicit = TraceContext(
            trace_id=EXPLICIT_TRACE_ID, parent_span_id=EXPLICIT_SPAN_ID
        )

        service.run(
            {}, deployed=LOAN_PRICING, folder_key=FOLDER_KEY, trace_context=explicit
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert (
            request.headers[TRACEPARENT]
            == f"00-{EXPLICIT_TRACE_ID}-{EXPLICIT_SPAN_ID}-01"
        )

    def test_explicit_trace_context_wins_over_uipath_trace_id(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
        ambient_span: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("UIPATH_TRACE_ID", AMBIENT_TRACE_ID)
        httpx_mock.add_response(url=evaluate_url, json=_response([]))
        explicit = TraceContext(
            trace_id=EXPLICIT_TRACE_ID, parent_span_id=EXPLICIT_SPAN_ID
        )

        service.run(
            {}, deployed=LOAN_PRICING, folder_key=FOLDER_KEY, trace_context=explicit
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert (
            request.headers[TRACEPARENT]
            == f"00-{EXPLICIT_TRACE_ID}-{EXPLICIT_SPAN_ID}-01"
        )

    def test_ambient_trace_is_used_without_trace_context(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
        ambient_span: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("UIPATH_TRACE_ID", raising=False)
        httpx_mock.add_response(url=evaluate_url, json=_response([]))

        service.run({}, deployed=LOAN_PRICING, folder_key=FOLDER_KEY)

        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[TRACEPARENT].startswith(f"00-{AMBIENT_TRACE_ID}-")

    def test_override_does_not_leak_into_the_next_call(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
        ambient_span: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("UIPATH_TRACE_ID", raising=False)
        httpx_mock.add_response(url=evaluate_url, json=_response([]))
        httpx_mock.add_response(url=evaluate_url, json=_response([]))
        explicit = TraceContext(
            trace_id=EXPLICIT_TRACE_ID, parent_span_id=EXPLICIT_SPAN_ID
        )

        service.run(
            {}, deployed=LOAN_PRICING, folder_key=FOLDER_KEY, trace_context=explicit
        )
        service.run({}, deployed=LOAN_PRICING, folder_key=FOLDER_KEY)

        first, second = httpx_mock.get_requests()
        assert EXPLICIT_TRACE_ID in first.headers[TRACEPARENT]
        assert second.headers[TRACEPARENT].startswith(f"00-{AMBIENT_TRACE_ID}-")

    async def test_explicit_trace_context_async(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
        ambient_span: None,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response([]))
        explicit = TraceContext(
            trace_id=EXPLICIT_TRACE_ID, parent_span_id=EXPLICIT_SPAN_ID
        )

        await service.run_async(
            {}, deployed=LOAN_PRICING, folder_key=FOLDER_KEY, trace_context=explicit
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert (
            request.headers[TRACEPARENT]
            == f"00-{EXPLICIT_TRACE_ID}-{EXPLICIT_SPAN_ID}-01"
        )

    def test_explicit_trace_context_on_debug_run(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        debug_url: str,
        ambient_span: None,
    ) -> None:
        httpx_mock.add_response(url=debug_url, json=_response([]))
        explicit = TraceContext(
            trace_id=EXPLICIT_TRACE_ID, parent_span_id=EXPLICIT_SPAN_ID
        )

        service.run(
            {}, debug=DebugRunContext(project_id="proj-1"), trace_context=explicit
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert (
            request.headers[TRACEPARENT]
            == f"00-{EXPLICIT_TRACE_ID}-{EXPLICIT_SPAN_ID}-01"
        )

    def test_trace_id_accepts_uuid_form_and_upper_case(self) -> None:
        context = TraceContext(
            trace_id="4BF92F35-77B3-4DA6-A3CE-929D0E0E4736",
            parent_span_id="00F067AA0BA902B7",
        )

        assert context.to_traceparent() == (
            f"00-{EXPLICIT_TRACE_ID}-{EXPLICIT_SPAN_ID}-01"
        )

    @pytest.mark.parametrize(
        ("trace_id", "parent_span_id", "message"),
        [
            ("abc", EXPLICIT_SPAN_ID, "trace_id must be 32 hex"),
            ("z" * 32, EXPLICIT_SPAN_ID, "trace_id must be 32 hex"),
            ("0" * 32, EXPLICIT_SPAN_ID, "trace_id must not be all zeros"),
            (EXPLICIT_TRACE_ID, "abc", "parent_span_id must be 16 hex"),
            (EXPLICIT_TRACE_ID, "0" * 16, "parent_span_id must not be all zeros"),
        ],
    )
    def test_rejects_malformed_ids(
        self, trace_id: str, parent_span_id: str, message: str
    ) -> None:
        with pytest.raises(ValidationError, match=message):
            TraceContext(trace_id=trace_id, parent_span_id=parent_span_id)
