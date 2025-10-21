import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services._base_service import BaseService
from uipath._utils.constants import HEADER_USER_AGENT


@pytest.fixture
def service(config: Config, execution_context: ExecutionContext) -> BaseService:
    return BaseService(config=config, execution_context=execution_context)


class TestBaseService:
    def test_init_base_service(self, service: BaseService):
        assert service is not None

    def test_base_service_default_headers(self, service: BaseService, secret: str):
        assert service.default_headers == {
            "Accept": "application/json",
            "Authorization": f"Bearer {secret}",
        }

    class TestRequest:
        def test_simple_request(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
            secret: str,
        ):
            endpoint = "/endpoint"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "test"},
            )

            response = service.request("GET", endpoint)

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "GET"
            assert sent_request.url == f"{base_url}{org}{tenant}{endpoint}"

            assert HEADER_USER_AGENT in sent_request.headers
            assert (
                sent_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.TestRequest.test_simple_request/{version}"
            )
            assert sent_request.headers["Authorization"] == f"Bearer {secret}"

            assert response is not None
            assert response.status_code == 200
            assert response.json() == {"test": "test"}

    class TestRequestAsync:
        @pytest.mark.anyio
        async def test_simple_request_async(
            self,
            httpx_mock: HTTPXMock,
            service: BaseService,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
            secret: str,
        ):
            endpoint = "/endpoint"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}{endpoint}",
                status_code=200,
                json={"test": "test"},
            )

            response = await service.request_async("GET", endpoint)

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "GET"
            assert sent_request.url == f"{base_url}{org}{tenant}{endpoint}"

            assert HEADER_USER_AGENT in sent_request.headers
            assert (
                sent_request.headers[HEADER_USER_AGENT]
                == f"UiPath.Python.Sdk/UiPath.Python.Sdk.Activities.TestRequestAsync.test_simple_request_async/{version}"
            )
            assert sent_request.headers["Authorization"] == f"Bearer {secret}"

            assert response is not None
            assert response.status_code == 200
            assert response.json() == {"test": "test"}
