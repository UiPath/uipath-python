import httpx
from pytest_httpx import HTTPXMock

from uipath.platform.orchestrator import get_server_version


class TestGetServerVersion:
    def test_success(self, httpx_mock: HTTPXMock):
        domain = "https://cloud.uipath.com"
        httpx_mock.add_response(
            url=f"{domain}/orchestrator_/api/status/version",
            method="GET",
            status_code=200,
            json={"version": "23.10.1.0"},
        )

        assert get_server_version(domain) == "23.10.1.0"

    def test_error_returns_none(self, httpx_mock: HTTPXMock):
        domain = "https://cloud.uipath.com"
        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        assert get_server_version(domain) is None
