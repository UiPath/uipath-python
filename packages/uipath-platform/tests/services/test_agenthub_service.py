import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.agenthub._agenthub_service import AgentHubService
from uipath.platform.orchestrator._folder_service import FolderService

RETIRED_MODEL = {
    "modelName": "gpt-4o-2024-05-13",
    "vendor": "OpenAi",
    "effectiveModel": "gpt-5.1-2025-11-13",
    "isDeprecated": True,
    "deprecationDetails": {
        "usageEndDate": "2026-09-30",
        "replacedBy": "gpt-5.1-2025-11-13",
    },
}


@pytest.fixture
def service(
    config: UiPathApiConfig, execution_context: UiPathExecutionContext
) -> AgentHubService:
    return AgentHubService(
        config=config,
        execution_context=execution_context,
        folder_service=FolderService(
            config=config, execution_context=execution_context
        ),
    )


@pytest.fixture
def discovery_url(base_url: str, org: str, tenant: str) -> str:
    return f"{base_url}{org}{tenant}/agenthub_/llm/api/discovery"


class TestGetAvailableLlmModels:
    def test_does_not_request_deprecated_models_by_default(
        self, httpx_mock: HTTPXMock, service: AgentHubService, discovery_url: str
    ) -> None:
        httpx_mock.add_response(url=discovery_url, json=[])

        service.get_available_llm_models()

        request = httpx_mock.get_request()
        assert request is not None
        assert "includeDeprecatedModels" not in request.url.params

    def test_requests_deprecated_models_when_asked(
        self, httpx_mock: HTTPXMock, service: AgentHubService, discovery_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{discovery_url}?includeDeprecatedModels=true",
            json=[RETIRED_MODEL],
        )

        models = service.get_available_llm_models(include_deprecated_models=True)

        assert [m.model_dump(by_alias=True) for m in models] == [RETIRED_MODEL]

    async def test_async_requests_deprecated_models_when_asked(
        self, httpx_mock: HTTPXMock, service: AgentHubService, discovery_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{discovery_url}?includeDeprecatedModels=true",
            json=[RETIRED_MODEL],
        )

        models = await service.get_available_llm_models_async(
            include_deprecated_models=True
        )

        assert [m.model_dump(by_alias=True) for m in models] == [RETIRED_MODEL]
