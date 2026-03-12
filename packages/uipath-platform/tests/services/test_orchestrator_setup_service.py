import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.orchestrator import OrchestratorSetupService


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
) -> OrchestratorSetupService:
    return OrchestratorSetupService(config=config, execution_context=execution_context)


class TestOrchestratorSetupServiceEnableFirstRun:
    @pytest.mark.parametrize("use_async", [False, True])
    async def test_enable_first_run_success(
        self,
        httpx_mock: HTTPXMock,
        service: OrchestratorSetupService,
        base_url: str,
        org: str,
        tenant: str,
        use_async: bool,
    ):
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/StudioWeb/TryEnableFirstRun",
            method="POST",
            status_code=200,
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/StudioWeb/AcquireLicense",
            method="POST",
            status_code=200,
        )

        if use_async:
            await service.enable_first_run_async()
        else:
            service.enable_first_run()

        requests = httpx_mock.get_requests()
        assert len(requests) == 2

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_enable_first_run_error_does_not_raise(
        self,
        httpx_mock: HTTPXMock,
        service: OrchestratorSetupService,
        base_url: str,
        org: str,
        tenant: str,
        use_async: bool,
    ):
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/StudioWeb/TryEnableFirstRun",
            method="POST",
            status_code=400,
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/StudioWeb/AcquireLicense",
            method="POST",
            status_code=400,
        )

        if use_async:
            await service.enable_first_run_async()
        else:
            service.enable_first_run()

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_enable_first_run_sends_bearer_token(
        self,
        httpx_mock: HTTPXMock,
        service: OrchestratorSetupService,
        base_url: str,
        org: str,
        tenant: str,
        secret: str,
        use_async: bool,
    ):
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/StudioWeb/TryEnableFirstRun",
            method="POST",
            status_code=200,
        )
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/api/StudioWeb/AcquireLicense",
            method="POST",
            status_code=200,
        )

        if use_async:
            await service.enable_first_run_async()
        else:
            service.enable_first_run()

        for req in httpx_mock.get_requests():
            assert req.headers["Authorization"] == f"Bearer {secret}"
