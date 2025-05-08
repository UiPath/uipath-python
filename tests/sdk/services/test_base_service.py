import importlib

import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services._base_service import BaseService
from uipath._utils.constants import HEADER_USER_AGENT

BASE_URL = "https://test.uipath.com"
ORG = "/org"
TENANT = "/tenant"
ENDPOINT = "/endpoint"
SECRET = "test_secret"


def config() -> Config:
    """Create a test configuration."""
    return Config(base_url=f"{BASE_URL}{ORG}{TENANT}", secret=SECRET)


try:
    version = importlib.metadata.version("uipath")
except importlib.metadata.PackageNotFoundError:
    version = "unknown"


class TestBaseService:
    def test_init_base_service(self):
        service = BaseService(config(), ExecutionContext())

        assert service is not None

    def test_base_service_default_headers(self):
        service = BaseService(config(), ExecutionContext())

        assert service.default_headers == {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {SECRET}",
        }

    class TestRequest:
        def test_simple_request(self, httpx_mock: HTTPXMock):
            httpx_mock.add_response(
                url=f"{BASE_URL}{ORG}{TENANT}{ENDPOINT}",
                status_code=200,
                json={"test": "test"},
            )

            service = BaseService(config(), ExecutionContext())
            response = service.request("GET", ENDPOINT)

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "GET"
            assert sent_request.url == f"{BASE_URL}{ORG}{TENANT}{ENDPOINT}"

            assert HEADER_USER_AGENT in sent_request.headers
            assert (
                sent_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.TestRequest.test_simple_request/{version}"
            )
            assert sent_request.headers["Authorization"] == f"Bearer {SECRET}"

            assert response is not None
            assert response.status_code == 200
            assert response.json() == {"test": "test"}

    class TestRequestAsync:
        @pytest.mark.anyio
        async def test_simple_request_async(self, httpx_mock: HTTPXMock):
            httpx_mock.add_response(
                url=f"{BASE_URL}{ORG}{TENANT}{ENDPOINT}",
                status_code=200,
                json={"test": "test"},
            )

            service = BaseService(config(), ExecutionContext())
            response = await service.request_async("GET", ENDPOINT)

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "GET"
            assert sent_request.url == f"{BASE_URL}{ORG}{TENANT}{ENDPOINT}"

            assert HEADER_USER_AGENT in sent_request.headers
            assert (
                sent_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.TestRequestAsync.test_simple_request_async/{version}"
            )
            assert sent_request.headers["Authorization"] == f"Bearer {SECRET}"

            assert response is not None
            assert response.status_code == 200
            assert response.json() == {"test": "test"}

    class TestRequestOrgScope:
        def test_simple_request(self, httpx_mock: HTTPXMock):
            httpx_mock.add_response(
                url=f"{BASE_URL}{ORG}{ENDPOINT}",
                status_code=200,
                json={"test": "test"},
            )

            service = BaseService(config(), ExecutionContext())
            response = service.request_org_scope("GET", ENDPOINT)

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "GET"
            assert sent_request.url == f"{BASE_URL}{ORG}{ENDPOINT}"

            assert HEADER_USER_AGENT in sent_request.headers
            assert (
                sent_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.TestRequestOrgScope.test_simple_request/{version}"
            )
            assert sent_request.headers["Authorization"] == f"Bearer {SECRET}"

            assert response is not None
            assert response.status_code == 200
            assert response.json() == {"test": "test"}

    class TestRequestOrgScopeAsync:
        @pytest.mark.anyio
        async def test_simple_request_async(self, httpx_mock: HTTPXMock):
            httpx_mock.add_response(
                url=f"{BASE_URL}{ORG}{ENDPOINT}",
                status_code=200,
                json={"test": "test"},
            )

            service = BaseService(config(), ExecutionContext())
            response = await service.request_org_scope_async("GET", ENDPOINT)

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "GET"
            assert sent_request.url == f"{BASE_URL}{ORG}{ENDPOINT}"

            assert HEADER_USER_AGENT in sent_request.headers
            assert (
                sent_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.TestRequestOrgScopeAsync.test_simple_request_async/{version}"
            )
            assert sent_request.headers["Authorization"] == f"Bearer {SECRET}"

            assert response is not None
            assert response.status_code == 200
            assert response.json() == {"test": "test"}
