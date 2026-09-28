import json
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.business_rules import (
    BusinessRulesService,
    BusinessRuleStatus,
)
from uipath.platform.constants import HEADER_FOLDER_KEY, HEADER_USER_AGENT
from uipath.platform.errors import EnrichedException

FOLDER_KEY = "5f1f1b0e-2b8a-4c1e-9b8e-1a2b3c4d5e6f"


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
    return BusinessRulesService(
        config=config,
        execution_context=execution_context,
        folders_service=folders_service,
    )


@pytest.fixture
def evaluate_url(base_url: str, org: str, tenant: str) -> str:
    return f"{base_url}{org}{tenant}/businessrules_/v1/business-rules/evaluate"


def _response(results: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
    return {
        "hasPartialSuccess": False,
        "stats": {"submitted": 1, "succeeded": 1, "failed": 0, "notEvaluated": 0},
        "results": results,
        "meta": {"timestamp": "2026-09-28T00:00:00Z"},
        **extra,
    }


class TestEvaluate:
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
                [
                    {
                        "id": "input-1",
                        "decisions": [
                            {
                                "decisionName": "RiskGrade",
                                "outputs": {"Grade": "B", "Rate": 3.5},
                            }
                        ],
                    }
                ],
                businessRuleName="Loan Pricing",
                version="1.0.3",
            ),
        )

        result = service.evaluate(
            "Loan Pricing",
            {"creditScore": 740},
            version="1.0.3",
            decision_names=["RiskGrade"],
            explain=True,
            folder_key=FOLDER_KEY,
        )

        assert result.status == BusinessRuleStatus.SUCCESS
        assert result.decisions[0].decision_name == "RiskGrade"
        assert result.decisions[0].outputs == {"Grade": "B", "Rate": 3.5}
        assert result.errors == []
        assert result.top_level_error is None
        assert result.business_rule_name == "Loan Pricing"
        assert result.version == "1.0.3"

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
            == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.BusinessRulesService.evaluate/{version}"
        )

    def test_omits_optional_fields(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response([]))

        service.evaluate("Loan Pricing", {}, folder_key=FOLDER_KEY)

        request = httpx_mock.get_request()
        assert request is not None
        body = json.loads(request.content)
        assert "version" not in body
        assert "decisionNames" not in body
        assert body["explain"] is False

    def test_resolves_folder_path_to_key(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        folders_service: Mock,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(url=evaluate_url, json=_response([]))

        service.evaluate("Loan Pricing", {}, folder_path="Finance/Loans")

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

        service.evaluate("Loan Pricing", {})

        folders_service.retrieve_folder_key.assert_not_called()
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == "env-folder-key"

    def test_requires_a_folder(self, service: BusinessRulesService) -> None:
        with pytest.raises(ValueError, match="folder is required"):
            service.evaluate("Loan Pricing", {})

    def test_rejects_both_folder_key_and_path(
        self, service: BusinessRulesService
    ) -> None:
        with pytest.raises(ValueError, match="Only one of"):
            service.evaluate(
                "Loan Pricing", {}, folder_key=FOLDER_KEY, folder_path="Finance"
            )

    @pytest.mark.parametrize(
        "rule_name",
        ["", "   ", "a/b", "a\\b", "a..b", "a%20b", "a\nb", "x" * 257],
    )
    def test_rejects_unsafe_rule_names(
        self, service: BusinessRulesService, rule_name: str
    ) -> None:
        with pytest.raises(ValueError, match="rule_name"):
            service.evaluate(rule_name, {}, folder_key=FOLDER_KEY)

    def test_rejects_oversized_input(self, service: BusinessRulesService) -> None:
        with pytest.raises(ValueError, match="256 keys"):
            service.evaluate(
                "Loan Pricing",
                {f"k{i}": i for i in range(257)},
                folder_key=FOLDER_KEY,
            )

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

        result = service.evaluate("Loan Pricing", {}, folder_key=FOLDER_KEY)

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

        result = service.evaluate("Loan Pricing", {}, folder_key=FOLDER_KEY)

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

        result = service.evaluate("Loan Pricing", {}, folder_key=FOLDER_KEY)

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

        with pytest.raises(EnrichedException) as exc:
            service.evaluate("Missing", {}, folder_key=FOLDER_KEY)

        assert exc.value.status_code == 404

    async def test_evaluate_async_resolves_folder_path(
        self,
        httpx_mock: HTTPXMock,
        service: BusinessRulesService,
        folders_service: Mock,
        evaluate_url: str,
    ) -> None:
        httpx_mock.add_response(
            url=evaluate_url,
            json=_response(
                [
                    {
                        "id": "input-1",
                        "decisions": [{"decisionName": "D", "outputs": {"x": 1}}],
                    }
                ]
            ),
        )

        result = await service.evaluate_async(
            "Loan Pricing", {"a": 1}, folder_path="Finance"
        )

        folders_service.retrieve_folder_key_async.assert_awaited_once_with("Finance")
        assert result.status == BusinessRuleStatus.SUCCESS
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY
