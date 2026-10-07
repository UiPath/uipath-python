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
    BusinessRuleCaller,
    BusinessRulesService,
    BusinessRuleStatus,
    TraceContext,
)
from uipath.platform.common._bindings import (
    GenericResourceOverwrite,
    ResourceOverwriteParser,
    _resource_overwrites,
)
from uipath.platform.common._config import UiPathConfig
from uipath.platform.constants import HEADER_FOLDER_KEY, HEADER_USER_AGENT
from uipath.platform.errors import EnrichedException

FOLDER_KEY = "5f1f1b0e-2b8a-4c1e-9b8e-1a2b3c4d5e6f"
TRACEPARENT = "x-uipath-traceparent-id"
RULE = "Loan Pricing"
JOB_KEY = "9d8c7b6a-5f4e-3d2c-1b0a-9f8e7d6c5b4a"


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
    monkeypatch.delenv("UIPATH_PROCESS_UUID", raising=False)
    monkeypatch.delenv("UIPATH_PROJECT_ID", raising=False)
    # Not a debug session unless a test says so, whatever uipath.json is nearby.
    monkeypatch.setattr(
        type(UiPathConfig), "is_rooted_to_debug_job", property(lambda self: False)
    )
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


def _response(result: dict[str, Any] | None = None, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"meta": {"timestamp": "2026-09-28T00:00:00Z"}, **extra}
    body["result"] = {"decisions": []} if result is None else result
    return body


def _one_decision(**outputs: Any) -> dict[str, Any]:
    return {"decisions": [{"decisionName": "RiskGrade", "outputs": outputs}]}


class TestRunContext:
    @pytest.mark.parametrize(
        "rule_name",
        ["", "   ", "a/b", "a\\b", "a..b", "a%20b", "a\nb", "x" * 257],
    )
    def test_rejects_unsafe_rule_names(
        self, service: BusinessRulesService, rule_name: str
    ) -> None:
        with pytest.raises(ValueError, match="name"):
            service.run(rule_name, {}, folder_key=FOLDER_KEY)

    @pytest.mark.parametrize("value", [["age", 14], "age=14", 14])
    def test_rejects_non_mapping_input(
        self, httpx_mock: HTTPXMock, service: BusinessRulesService, value: Any
    ) -> None:
        with pytest.raises(ValueError, match="input must be a mapping"):
            service.run(RULE, value, folder_key=FOLDER_KEY)

        assert httpx_mock.get_requests() == []

    def test_rejects_oversized_input(self, service: BusinessRulesService) -> None:
        with pytest.raises(ValueError, match="256 keys"):
            service.run(RULE, {f"k{i}": i for i in range(257)}, folder_key=FOLDER_KEY)


class TestFolder:
    def test_resolves_folder_path_to_key(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        folders_service: Mock,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(RULE, {}, folder_path="Finance/Loans")

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
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(RULE, {})

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
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(RULE, {})

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
        httpx_mock.add_response(url=evaluate_url, json=_response())

        await service.run_async(RULE, {})

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
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(RULE, {})

        folders_service.retrieve_folder_key.assert_not_called()
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == "env-folder-key"

    def test_deployed_requires_a_folder(
        self, httpx_mock: HTTPXMock, service: BusinessRulesService
    ) -> None:
        with pytest.raises(ValueError, match="deployed business rule"):
            service.run(RULE, {})

        assert httpx_mock.get_requests() == []

    def test_deployed_rejects_a_blank_folder_key(
        self, httpx_mock: HTTPXMock, service: BusinessRulesService
    ) -> None:
        with pytest.raises(ValueError, match="deployed business rule"):
            service.run(RULE, {}, folder_key="   ")

        assert httpx_mock.get_requests() == []

    def test_sends_no_organization_unit_id(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(RULE, {}, folder_key=FOLDER_KEY)

        request = httpx_mock.get_request()
        assert request is not None
        assert "x-uipath-organizationunitid" not in request.headers

    def test_rejects_both_folder_key_and_path(
        self, service: BusinessRulesService
    ) -> None:
        with pytest.raises(ValueError, match="Only one of"):
            service.run(RULE, {}, folder_key=FOLDER_KEY, folder_path="Finance")


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
            "Loan Pricing",
            {"creditScore": 740},
            version="1.0.3",
            decision_names=["RiskGrade"],
            folder_key=FOLDER_KEY,
        )

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
            "input": {"creditScore": 740},
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
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(RULE, {}, version="  ", folder_key=FOLDER_KEY)

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert body == {"businessRuleName": RULE, "input": {}}

    def test_sends_no_explain_or_batch(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(RULE, {"a": 1}, folder_key=FOLDER_KEY)

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert "explain" not in body
        assert "inputs" not in body

    async def test_run_async_resolves_folder_path(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        folders_service: Mock,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response(_one_decision(x=1)))

        result = await service.run_async(RULE, {"a": 1}, folder_path="Finance")

        folders_service.retrieve_folder_key_async.assert_awaited_once_with("Finance")
        assert result.status == BusinessRuleStatus.SUCCESS
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY


class TestCaller:
    def test_defaults_from_the_environment(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("UIPATH_PROCESS_UUID", "release-key")
        monkeypatch.setenv("UIPATH_JOB_KEY", JOB_KEY)
        monkeypatch.setenv("UIPATH_FOLDER_KEY", "caller-folder-key")
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(RULE, {}, folder_key=FOLDER_KEY)

        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.content)["caller"] == {
            "resourceKey": "release-key",
            "runKey": JOB_KEY,
            "folderKey": "caller-folder-key",
        }
        # The rule's folder, not the caller's, scopes the run.
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY

    def test_explicit_fields_win_over_the_environment(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("UIPATH_PROCESS_UUID", "release-key")
        monkeypatch.setenv("UIPATH_JOB_KEY", JOB_KEY)
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(
            RULE,
            {},
            folder_key=FOLDER_KEY,
            caller=BusinessRuleCaller(run_key="agent-run", folder_key="agent-folder"),
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.content)["caller"] == {
            "resourceKey": "release-key",
            "runKey": "agent-run",
            "folderKey": "agent-folder",
        }

    def test_blank_fields_are_left_out(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(
            RULE,
            {},
            folder_key=FOLDER_KEY,
            caller=BusinessRuleCaller(resource_key="release-key", run_key="  "),
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.content)["caller"] == {"resourceKey": "release-key"}

    def test_no_caller_without_any_value(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(RULE, {}, folder_key=FOLDER_KEY)

        request = httpx_mock.get_request()
        assert request is not None
        assert "caller" not in json.loads(request.content)


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
                {
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
            ),
        )

        result = service.run(RULE, {}, folder_key=FOLDER_KEY)

        assert result.status == BusinessRuleStatus.PARTIAL_SUCCESS
        assert result.decisions[1].error is not None
        assert result.decisions[1].error.code == "DECISION_FAILED"

    def test_every_decision_failing_is_all_failed(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(
            url=evaluate_url,
            status_code=207,
            json=_response(
                {
                    "decisions": [
                        {
                            "decisionName": "Payment",
                            "error": {"code": "DECISION_FAILED", "message": "x"},
                        }
                    ]
                }
            ),
        )

        result = service.run(RULE, {}, folder_key=FOLDER_KEY)

        assert result.status == BusinessRuleStatus.ALL_FAILED

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
                {
                    "errors": [
                        {
                            "code": "INPUT_VALIDATION_FAILED",
                            "message": "creditScore must be a number",
                        }
                    ]
                }
            ),
        )

        result = service.run(RULE, {}, folder_key=FOLDER_KEY)

        assert result.status == BusinessRuleStatus.ALL_FAILED
        assert result.errors[0].code == "INPUT_VALIDATION_FAILED"

    def test_carries_the_top_level_error(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(
            url=evaluate_url,
            status_code=207,
            json=_response(
                {"errors": [{"code": "INPUT_FAILED", "message": "x"}]},
                error={"code": "UPSTREAM_ERROR", "message": "y"},
            ),
        )

        result = service.run(RULE, {}, folder_key=FOLDER_KEY)

        assert result.top_level_error == "UPSTREAM_ERROR"

    def test_raises_when_the_result_is_missing(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(
            url=evaluate_url, json={"meta": {"timestamp": "2026-09-28T00:00:00Z"}}
        )

        with pytest.raises(ValueError, match="did not include a result"):
            service.run(RULE, {}, folder_key=FOLDER_KEY)

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

        with pytest.raises(EnrichedException) as exc:
            service.run("Missing", {}, folder_key=FOLDER_KEY)

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
        httpx_mock.add_response(url=evaluate_url, json=_response())
        explicit = TraceContext(
            trace_id=EXPLICIT_TRACE_ID, parent_span_id=EXPLICIT_SPAN_ID
        )

        service.run(RULE, {}, folder_key=FOLDER_KEY, trace_context=explicit)

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
        httpx_mock.add_response(url=evaluate_url, json=_response())
        explicit = TraceContext(
            trace_id=EXPLICIT_TRACE_ID, parent_span_id=EXPLICIT_SPAN_ID
        )

        service.run(RULE, {}, folder_key=FOLDER_KEY, trace_context=explicit)

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
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(RULE, {}, folder_key=FOLDER_KEY)

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
        httpx_mock.add_response(url=evaluate_url, json=_response())
        httpx_mock.add_response(url=evaluate_url, json=_response())
        explicit = TraceContext(
            trace_id=EXPLICIT_TRACE_ID, parent_span_id=EXPLICIT_SPAN_ID
        )

        service.run(RULE, {}, folder_key=FOLDER_KEY, trace_context=explicit)
        service.run(RULE, {}, folder_key=FOLDER_KEY)

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
        httpx_mock.add_response(url=evaluate_url, json=_response())
        explicit = TraceContext(
            trace_id=EXPLICIT_TRACE_ID, parent_span_id=EXPLICIT_SPAN_ID
        )

        await service.run_async(RULE, {}, folder_key=FOLDER_KEY, trace_context=explicit)

        request = httpx_mock.get_request()
        assert request is not None
        assert (
            request.headers[TRACEPARENT]
            == f"00-{EXPLICIT_TRACE_ID}-{EXPLICIT_SPAN_ID}-01"
        )

    def test_explicit_trace_context_survives_a_retry(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
        ambient_span: None,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, status_code=503)
        httpx_mock.add_response(url=evaluate_url, json=_response())
        explicit = TraceContext(
            trace_id=EXPLICIT_TRACE_ID, parent_span_id=EXPLICIT_SPAN_ID
        )

        service.run(RULE, {}, folder_key=FOLDER_KEY, trace_context=explicit)

        first, second = httpx_mock.get_requests()
        expected = f"00-{EXPLICIT_TRACE_ID}-{EXPLICIT_SPAN_ID}-01"
        assert first.headers[TRACEPARENT] == expected
        assert second.headers[TRACEPARENT] == expected

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


@pytest.fixture
def rule_override() -> Iterator[None]:
    overwrite = GenericResourceOverwrite(
        resource_type="businessRule",
        name="Loan Pricing EU",
        folder_path="Finance/EU",
    )
    token = _resource_overwrites.set({"businessRule.Loan Pricing": overwrite})
    try:
        yield
    finally:
        _resource_overwrites.reset(token)


class TestResourceOverride:
    def test_parser_accepts_business_rule_bindings(self) -> None:
        overwrite = ResourceOverwriteParser.parse(
            "businessRule.Loan Pricing",
            {"name": "Loan Pricing EU", "folderPath": "Finance/EU"},
        )

        assert overwrite.resource_identifier == "Loan Pricing EU"
        assert overwrite.folder_identifier == "Finance/EU"

    def test_override_replaces_rule_name_and_folder(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        folders_service: Mock,
        evaluate_url: str,
        rule_override: None,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(RULE, {}, folder_path="Finance")

        folders_service.retrieve_folder_key.assert_called_once_with("Finance/EU")
        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.content)["businessRuleName"] == "Loan Pricing EU"
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY

    async def test_override_applies_to_run_async(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        folders_service: Mock,
        evaluate_url: str,
        rule_override: None,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response())

        await service.run_async(RULE, {}, folder_path="Finance")

        folders_service.retrieve_folder_key_async.assert_awaited_once_with("Finance/EU")
        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.content)["businessRuleName"] == "Loan Pricing EU"

    def test_override_folder_replaces_callers_folder_key(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        folders_service: Mock,
        evaluate_url: str,
        rule_override: None,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(RULE, {}, folder_key="callers-folder-key")

        folders_service.retrieve_folder_key.assert_called_once_with("Finance/EU")
        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.content)["businessRuleName"] == "Loan Pricing EU"
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY

    async def test_override_folder_replaces_callers_folder_key_async(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        folders_service: Mock,
        evaluate_url: str,
        rule_override: None,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response())

        await service.run_async(RULE, {}, folder_key="callers-folder-key")

        folders_service.retrieve_folder_key_async.assert_awaited_once_with("Finance/EU")
        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.content)["businessRuleName"] == "Loan Pricing EU"
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY

    def test_callers_folder_key_kept_without_a_matching_override(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        folders_service: Mock,
        evaluate_url: str,
        rule_override: None,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run("Risk Tier", {}, folder_key="callers-folder-key")

        folders_service.retrieve_folder_key.assert_not_called()
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == "callers-folder-key"

    def test_other_rules_are_not_overridden(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        folders_service: Mock,
        evaluate_url: str,
        rule_override: None,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run("Risk Tier", {}, folder_path="Finance")

        folders_service.retrieve_folder_key.assert_called_once_with("Finance")
        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.content)["businessRuleName"] == "Risk Tier"


PROJECT_ID = "041e6279-8a51-4aec-b2fa-6786704eba19"


@pytest.fixture
def studio_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Studio debug session: the project being debugged and its job."""
    monkeypatch.setenv("UIPATH_PROJECT_ID", PROJECT_ID)
    monkeypatch.setenv("UIPATH_JOB_KEY", JOB_KEY)


@pytest.fixture
def rooted_to_debug_job(monkeypatch: pytest.MonkeyPatch) -> None:
    """A deployed process running under a debug session (e.g. a solution debug)."""
    monkeypatch.setattr(
        type(UiPathConfig), "is_rooted_to_debug_job", property(lambda self: True)
    )
    monkeypatch.setenv("UIPATH_JOB_KEY", JOB_KEY)


class TestDebug:
    def test_studio_session_runs_the_project_rule(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        debug_url: str,
        studio_debug: None,
    ) -> None:
        httpx_mock.add_response(
            url=debug_url,
            method="POST",
            json=_response(
                _one_decision(x=1), projectId=PROJECT_ID, fileName="Business rule.dmn"
            ),
        )

        result = service.run(RULE, {"a": 1}, decision_names=["RiskGrade"])

        assert result.status == BusinessRuleStatus.SUCCESS
        assert result.project_id == PROJECT_ID
        assert result.file_name == "Business rule.dmn"
        assert result.business_rule_name is None

        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.content) == {
            "businessRuleName": RULE,
            "decisionNames": ["RiskGrade"],
            "input": {"a": 1},
        }
        assert request.headers["x-uipath-jobkey"] == JOB_KEY

    def test_job_rooted_to_a_debug_session_runs_the_project_rule(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        debug_url: str,
        rooted_to_debug_job: None,
    ) -> None:
        httpx_mock.add_response(url=debug_url, json=_response())

        service.run(RULE, {})

        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["x-uipath-jobkey"] == JOB_KEY

    def test_sends_no_folder_version_or_caller(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        folders_service: Mock,
        debug_url: str,
        studio_debug: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("UIPATH_FOLDER_KEY", "env-folder-key")
        monkeypatch.setenv("UIPATH_PROCESS_UUID", "release-key")
        httpx_mock.add_response(url=debug_url, json=_response())

        service.run(
            RULE,
            {},
            version="1.0.0",
            caller=BusinessRuleCaller(run_key="agent-run"),
        )

        folders_service.retrieve_folder_key.assert_not_called()
        request = httpx_mock.get_request()
        assert request is not None
        # The service takes the job's folders from its lineage.
        assert HEADER_FOLDER_KEY not in request.headers
        assert "x-uipath-organizationunitid" not in request.headers
        assert "x-uipath-folderpath" not in request.headers
        body = json.loads(request.content)
        assert "version" not in body
        assert "caller" not in body

    @pytest.mark.parametrize(
        "folder", [{"folder_key": FOLDER_KEY}, {"folder_path": "Finance"}]
    )
    def test_a_named_folder_runs_the_deployed_rule(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
        studio_debug: None,
        folder: dict[str, str],
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(RULE, {}, **folder)

        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY
        assert "x-uipath-jobkey" not in request.headers

    def test_a_blank_folder_does_not_count_as_named(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        debug_url: str,
        studio_debug: None,
    ) -> None:
        httpx_mock.add_response(url=debug_url, json=_response())

        service.run(RULE, {}, folder_key="  ")

        assert httpx_mock.get_request() is not None

    def test_a_session_without_a_job_key_runs_deployed(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Running a project locally: no job, so no lineage to read it from.
        monkeypatch.setenv("UIPATH_PROJECT_ID", PROJECT_ID)
        monkeypatch.setenv("UIPATH_JOB_KEY", "   ")
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(RULE, {}, folder_key=FOLDER_KEY)

        assert httpx_mock.get_request() is not None

    def test_a_deployed_job_runs_deployed(
        self,
        httpx_mock: HTTPXMock,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: Mock,
        evaluate_url: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("UIPATH_JOB_KEY", JOB_KEY)
        monkeypatch.setenv("UIPATH_FOLDER_KEY", "env-folder-key")
        service = BusinessRulesService(config, execution_context, folders_service)
        httpx_mock.add_response(url=evaluate_url, json=_response())

        service.run(RULE, {})

        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == "env-folder-key"
        assert "x-uipath-jobkey" not in request.headers

    def test_rejects_unsafe_rule_name(
        self, httpx_mock: HTTPXMock, service: BusinessRulesService, studio_debug: None
    ) -> None:
        with pytest.raises(ValueError, match="name"):
            service.run("a/b", {})

        assert httpx_mock.get_requests() == []

    def test_override_applies_to_debug_runs(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        debug_url: str,
        studio_debug: None,
        rule_override: None,
    ) -> None:
        httpx_mock.add_response(url=debug_url, json=_response())

        service.run(RULE, {})

        request = httpx_mock.get_request()
        assert request is not None
        assert json.loads(request.content)["businessRuleName"] == "Loan Pricing EU"
        assert HEADER_FOLDER_KEY not in request.headers

    def test_retries_like_any_platform_call(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        debug_url: str,
        studio_debug: None,
    ) -> None:
        httpx_mock.add_response(url=debug_url, status_code=503)
        httpx_mock.add_response(url=debug_url, json=_response(_one_decision(x=1)))

        result = service.run(RULE, {})

        assert result.status == BusinessRuleStatus.SUCCESS
        assert len(httpx_mock.get_requests()) == 2

    def test_explicit_trace_context_on_debug_run(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        debug_url: str,
        studio_debug: None,
        ambient_span: None,
    ) -> None:
        httpx_mock.add_response(url=debug_url, json=_response())
        explicit = TraceContext(
            trace_id=EXPLICIT_TRACE_ID, parent_span_id=EXPLICIT_SPAN_ID
        )

        service.run(RULE, {}, trace_context=explicit)

        request = httpx_mock.get_request()
        assert request is not None
        assert (
            request.headers[TRACEPARENT]
            == f"00-{EXPLICIT_TRACE_ID}-{EXPLICIT_SPAN_ID}-01"
        )

    async def test_run_async_debug(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        debug_url: str,
        studio_debug: None,
    ) -> None:
        httpx_mock.add_response(url=debug_url, json=_response(projectId=PROJECT_ID))

        result = await service.run_async(RULE, {})

        assert result.project_id == PROJECT_ID
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers["x-uipath-jobkey"] == JOB_KEY
