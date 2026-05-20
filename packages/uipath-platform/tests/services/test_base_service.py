import pytest
from opentelemetry import trace as otel_trace
from opentelemetry.sdk.trace import TracerProvider
from pytest_httpx import HTTPXMock
from uipath.core.feature_flags import FeatureFlags

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.common._base_service import BaseService
from uipath.platform.common.constants import HEADER_USER_AGENT
from uipath.platform.errors import EnrichedException


@pytest.fixture
def service(
    config: UiPathApiConfig, execution_context: UiPathExecutionContext
) -> BaseService:
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


class TestRetryBehavior:
    """Integration tests for retry behavior in BaseService."""

    def _url(self, base_url: str, org: str, tenant: str) -> str:
        return f"{base_url}{org}{tenant}/endpoint"

    def test_429_with_retry_after_retried(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        url = self._url(base_url, org, tenant)
        httpx_mock.add_response(url=url, status_code=429, headers={"retry-after": "0"})
        httpx_mock.add_response(url=url, status_code=200, json={"ok": True})

        response = service.request("GET", "/endpoint")
        assert response.status_code == 200
        assert len(httpx_mock.get_requests()) == 2

    def test_503_retried(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        url = self._url(base_url, org, tenant)
        httpx_mock.add_response(url=url, status_code=503)
        httpx_mock.add_response(url=url, status_code=200, json={"ok": True})

        response = service.request("GET", "/endpoint")
        assert response.status_code == 200
        assert len(httpx_mock.get_requests()) == 2

    def test_400_not_retried(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        url = self._url(base_url, org, tenant)
        httpx_mock.add_response(url=url, status_code=400)

        with pytest.raises(EnrichedException) as exc_info:
            service.request("GET", "/endpoint")
        assert exc_info.value.status_code == 400
        assert len(httpx_mock.get_requests()) == 1

    def test_404_not_retried(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        url = self._url(base_url, org, tenant)
        httpx_mock.add_response(url=url, status_code=404)

        with pytest.raises(EnrichedException) as exc_info:
            service.request("GET", "/endpoint")
        assert exc_info.value.status_code == 404
        assert len(httpx_mock.get_requests()) == 1

    def test_500_not_retried(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        url = self._url(base_url, org, tenant)
        httpx_mock.add_response(url=url, status_code=500)

        with pytest.raises(EnrichedException) as exc_info:
            service.request("GET", "/endpoint")
        assert exc_info.value.status_code == 500
        assert len(httpx_mock.get_requests()) == 1

    def test_max_retries_exhausted(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        url = self._url(base_url, org, tenant)
        for _ in range(5):
            httpx_mock.add_response(
                url=url, status_code=429, headers={"retry-after": "0"}
            )

        with pytest.raises(EnrichedException) as exc_info:
            service.request("GET", "/endpoint")
        assert exc_info.value.status_code == 429
        assert len(httpx_mock.get_requests()) == 5

    def test_502_retried(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        url = self._url(base_url, org, tenant)
        httpx_mock.add_response(url=url, status_code=502)
        httpx_mock.add_response(url=url, status_code=200, json={"ok": True})

        response = service.request("GET", "/endpoint")
        assert response.status_code == 200
        assert len(httpx_mock.get_requests()) == 2

    @pytest.mark.anyio
    async def test_429_retried_async(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        url = self._url(base_url, org, tenant)
        httpx_mock.add_response(url=url, status_code=429, headers={"retry-after": "0"})
        httpx_mock.add_response(url=url, status_code=200, json={"ok": True})

        response = await service.request_async("GET", "/endpoint")
        assert response.status_code == 200
        assert len(httpx_mock.get_requests()) == 2

    @pytest.mark.anyio
    async def test_503_retried_async(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        url = self._url(base_url, org, tenant)
        httpx_mock.add_response(url=url, status_code=503)
        httpx_mock.add_response(url=url, status_code=200, json={"ok": True})

        response = await service.request_async("GET", "/endpoint")
        assert response.status_code == 200
        assert len(httpx_mock.get_requests()) == 2

    @pytest.mark.anyio
    async def test_400_not_retried_async(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        url = self._url(base_url, org, tenant)
        httpx_mock.add_response(url=url, status_code=400)

        with pytest.raises(EnrichedException) as exc_info:
            await service.request_async("GET", "/endpoint")
        assert exc_info.value.status_code == 400
        assert len(httpx_mock.get_requests()) == 1

    @pytest.mark.anyio
    async def test_max_retries_exhausted_async(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        base_url: str,
        org: str,
        tenant: str,
    ):
        url = self._url(base_url, org, tenant)
        for _ in range(5):
            httpx_mock.add_response(
                url=url, status_code=429, headers={"retry-after": "0"}
            )

        with pytest.raises(EnrichedException) as exc_info:
            await service.request_async("GET", "/endpoint")
        assert exc_info.value.status_code == 429
        assert len(httpx_mock.get_requests()) == 5


class TestServiceUrlOverride:
    def test_request_uses_override_url(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        monkeypatch: pytest.MonkeyPatch,
        version: str,
    ) -> None:
        monkeypatch.setenv("UIPATH_SERVICE_URL_AGENTHUB", "http://localhost:5200")
        monkeypatch.setenv("UIPATH_TENANT_ID", "tenant-123")
        monkeypatch.setenv("UIPATH_ORGANIZATION_ID", "org-456")

        httpx_mock.add_response(
            url="http://localhost:5200/llm/api/chat/completions",
            status_code=200,
            json={"result": "ok"},
        )

        response = service.request("POST", "/agenthub_/llm/api/chat/completions")

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert str(sent_request.url) == "http://localhost:5200/llm/api/chat/completions"
        assert sent_request.headers["X-UiPath-Internal-TenantId"] == "tenant-123"
        assert sent_request.headers["X-UiPath-Internal-AccountId"] == "org-456"
        assert response.status_code == 200

    def test_request_no_override_uses_normal_scoping(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        base_url: str,
        org: str,
        tenant: str,
        version: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("UIPATH_SERVICE_URL_ORCHESTRATOR", raising=False)

        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets",
            status_code=200,
            json={"value": []},
        )

        response = service.request("GET", "/orchestrator_/odata/Buckets")

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert (
            str(sent_request.url)
            == f"{base_url}{org}{tenant}/orchestrator_/odata/Buckets"
        )
        assert response.status_code == 200


_TRACE_PARENT_HEADER = "x-uipath-traceparent-id"


class TestTraceContextHeader:
    """`x-uipath-traceparent-id` must stay off the wire unless explicitly opted in.

    When the header is present, downstream services (LLM Gateway,
    /agentsruntime_/guardrails/validate, etc.) emit child spans tied to the
    propagated parent. That backend behavior pre-existed but only became
    user-visible once this header started shipping on every BaseService call —
    see AL-441, where helix-v2 emits permission-restricted child spans under
    LLMOps guardrail-evaluation parents.
    """

    @pytest.fixture(autouse=True)
    def _tracer_provider(self) -> None:
        # Default OTel ProxyTracer hands back NonRecording spans, which makes
        # the trace context inert. Install a real SDK provider so any span we
        # would propagate is observable on the wire.
        otel_trace.set_tracer_provider(TracerProvider())

    @pytest.fixture(autouse=True)
    def _reset_flags(self) -> None:
        FeatureFlags.reset_flags()
        yield
        FeatureFlags.reset_flags()

    def test_header_not_sent_when_flag_off(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/endpoint", status_code=200, json={}
        )
        tracer = otel_trace.get_tracer(__name__)
        with tracer.start_as_current_span("client-span"):
            service.request("GET", "/endpoint")

        sent = httpx_mock.get_request()
        assert sent is not None
        assert _TRACE_PARENT_HEADER not in sent.headers

    def test_header_sent_when_flag_on(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        FeatureFlags.configure_flags({"EnableTraceContextHeaders": True})
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/endpoint", status_code=200, json={}
        )
        tracer = otel_trace.get_tracer(__name__)
        with tracer.start_as_current_span("client-span"):
            service.request("GET", "/endpoint")

        sent = httpx_mock.get_request()
        assert sent is not None
        assert _TRACE_PARENT_HEADER in sent.headers
        assert sent.headers[_TRACE_PARENT_HEADER].startswith("00-")

    @pytest.mark.anyio
    async def test_header_not_sent_when_flag_off_async(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/endpoint", status_code=200, json={}
        )
        tracer = otel_trace.get_tracer(__name__)
        with tracer.start_as_current_span("client-span"):
            await service.request_async("GET", "/endpoint")

        sent = httpx_mock.get_request()
        assert sent is not None
        assert _TRACE_PARENT_HEADER not in sent.headers


class TestServiceUrlOverrideAsync:
    @pytest.mark.anyio
    async def test_request_async_uses_override_url(
        self,
        httpx_mock: HTTPXMock,
        service: BaseService,
        monkeypatch: pytest.MonkeyPatch,
        version: str,
    ) -> None:
        monkeypatch.setenv("UIPATH_SERVICE_URL_AGENTHUB", "http://localhost:5200")
        monkeypatch.setenv("UIPATH_TENANT_ID", "tenant-123")
        monkeypatch.setenv("UIPATH_ORGANIZATION_ID", "org-456")

        httpx_mock.add_response(
            url="http://localhost:5200/llm/api/chat/completions",
            status_code=200,
            json={"result": "ok"},
        )

        response = await service.request_async(
            "POST", "/agenthub_/llm/api/chat/completions"
        )

        sent_request = httpx_mock.get_request()
        assert sent_request is not None
        assert str(sent_request.url) == "http://localhost:5200/llm/api/chat/completions"
        assert sent_request.headers["X-UiPath-Internal-TenantId"] == "tenant-123"
        assert sent_request.headers["X-UiPath-Internal-AccountId"] == "org-456"
        assert response.status_code == 200
