import httpx
from pytest_httpx import HTTPXMock

from uipath.platform.orchestrator import StudioWebService

TENANT_URL = "https://cloud.uipath.com/org/tenant"
ENABLE_FIRST_RUN_URL_1 = f"{TENANT_URL}/orchestrator_/api/StudioWeb/TryEnableFirstRun"
ENABLE_FIRST_RUN_URL_2 = f"{TENANT_URL}/orchestrator_/api/StudioWeb/AcquireLicense"
ACCESS_TOKEN = "test-access-token"


class TestStudioWebServiceEnableFirstRun:
    def test_enable_first_run_success(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=ENABLE_FIRST_RUN_URL_1, method="POST", status_code=200
        )
        httpx_mock.add_response(
            url=ENABLE_FIRST_RUN_URL_2, method="POST", status_code=200
        )

        StudioWebService.enable_first_run(
            tenant_url=TENANT_URL, access_token=ACCESS_TOKEN
        )

        requests = httpx_mock.get_requests()
        assert len(requests) == 2

    def test_enable_first_run_error_does_not_raise(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=ENABLE_FIRST_RUN_URL_1, method="POST", status_code=400
        )
        httpx_mock.add_response(
            url=ENABLE_FIRST_RUN_URL_2, method="POST", status_code=400
        )

        StudioWebService.enable_first_run(
            tenant_url=TENANT_URL, access_token=ACCESS_TOKEN
        )

    def test_enable_first_run_sends_bearer_token(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=ENABLE_FIRST_RUN_URL_1, method="POST", status_code=200
        )
        httpx_mock.add_response(
            url=ENABLE_FIRST_RUN_URL_2, method="POST", status_code=200
        )

        StudioWebService.enable_first_run(
            tenant_url=TENANT_URL, access_token=ACCESS_TOKEN
        )

        for req in httpx_mock.get_requests():
            assert req.headers["Authorization"] == f"Bearer {ACCESS_TOKEN}"


class TestStudioWebServiceGetServerVersion:
    def test_get_server_version_success(self, httpx_mock: HTTPXMock):
        domain = "https://cloud.uipath.com"
        httpx_mock.add_response(
            url=f"{domain}/orchestrator_/api/status/version",
            method="GET",
            status_code=200,
            json={"version": "23.10.1.0"},
        )

        assert StudioWebService.get_server_version(domain=domain) == "23.10.1.0"

    def test_get_server_version_error_returns_none(self, httpx_mock: HTTPXMock):
        domain = "https://cloud.uipath.com"
        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        assert StudioWebService.get_server_version(domain=domain) is None
