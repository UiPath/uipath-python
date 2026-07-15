"""Tests for the IXP design-time transport foundation (``platform/document_projects/_transport``).

Cover the design-time transport conventions this layer enforces:
the ``du_/api/designtimeapi`` base path, the mandatory ``api-version=1.0`` query
param, strict path-segment percent-encoding, ``{}`` as the empty write body,
multipart ``file`` upload, binary download, and — the load-bearing one — that
writes are NOT retried while idempotent GETs are.
"""

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.document_projects import IxpDesigntimeService
from uipath.platform.errors import EnrichedException


@pytest.fixture
def ixp_service(
    config: UiPathApiConfig, execution_context: UiPathExecutionContext
) -> IxpDesigntimeService:
    return IxpDesigntimeService(config=config, execution_context=execution_context)


class TestDesigntimeUrl:
    def test_get_builds_designtime_url_with_api_version(
        self,
        httpx_mock: HTTPXMock,
        ixp_service: IxpDesigntimeService,
    ) -> None:
        httpx_mock.add_response(json={"value": []})

        ixp_service._get(ixp_service._endpoint("/api/projects"))

        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "GET"
        assert request.url.path == "/org/tenant/du_/api/designtimeapi/api/projects"
        assert request.url.params.get("api-version") == "1.0"

    def test_path_segments_are_percent_encoded(
        self,
        httpx_mock: HTTPXMock,
        ixp_service: IxpDesigntimeService,
    ) -> None:
        httpx_mock.add_response(json={})

        # A project name with a space and a slash must survive as %20 / %2F —
        # not split into extra path segments, not double-encoded.
        ixp_service._get(ixp_service._endpoint("/api/projects/{name}", name="a b/c"))

        request = httpx_mock.get_request()
        assert request is not None
        assert b"/api/projects/a%20b%2Fc" in request.url.raw_path


class TestWriteBody:
    def test_post_sends_empty_object_when_no_body(
        self,
        httpx_mock: HTTPXMock,
        ixp_service: IxpDesigntimeService,
    ) -> None:
        httpx_mock.add_response(json={})

        ixp_service._post(
            ixp_service._endpoint("/api/projects/{name}/prompt", name="p")
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "POST"
        assert request.content == b"{}"
        assert request.headers["content-type"] == "application/json"


class TestRetryPolicy:
    def test_post_not_retried_on_transient_error(
        self,
        httpx_mock: HTTPXMock,
        ixp_service: IxpDesigntimeService,
    ) -> None:
        # 502 is a normally-retryable status, but writes must not be retried.
        httpx_mock.add_response(status_code=502)

        with pytest.raises(EnrichedException) as exc_info:
            ixp_service._post(
                ixp_service._endpoint("/api/projects"), body={"Name": "p"}
            )

        assert exc_info.value.status_code == 502
        assert len(httpx_mock.get_requests()) == 1

    def test_delete_not_retried_on_transient_error(
        self,
        httpx_mock: HTTPXMock,
        ixp_service: IxpDesigntimeService,
    ) -> None:
        httpx_mock.add_response(status_code=502)

        with pytest.raises(EnrichedException) as exc_info:
            ixp_service._delete(ixp_service._endpoint("/api/projects/{name}", name="p"))

        assert exc_info.value.status_code == 502
        assert len(httpx_mock.get_requests()) == 1

    def test_get_retried_on_transient_error(
        self,
        httpx_mock: HTTPXMock,
        ixp_service: IxpDesigntimeService,
    ) -> None:
        # retry-after: 0 keeps the test fast while still exercising the retry.
        httpx_mock.add_response(status_code=429, headers={"retry-after": "0"})
        httpx_mock.add_response(status_code=200, json={"value": []})

        response = ixp_service._get(ixp_service._endpoint("/api/projects"))

        assert response.status_code == 200
        assert len(httpx_mock.get_requests()) == 2


class TestUploadDownload:
    def test_upload_uses_file_multipart_field(
        self,
        httpx_mock: HTTPXMock,
        ixp_service: IxpDesigntimeService,
    ) -> None:
        httpx_mock.add_response(json={"DocumentId": "d", "AttachmentRef": "r"})

        ixp_service._upload(
            ixp_service._endpoint("/api/projects/{name}/documents", name="p"),
            filename="invoice.pdf",
            content=b"%PDF-1.7 data",
            content_type="application/pdf",
        )

        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "POST"
        assert request.headers["content-type"].startswith("multipart/form-data")
        assert b'name="file"' in request.content
        assert b'filename="invoice.pdf"' in request.content
        assert b"%PDF-1.7 data" in request.content

    def test_download_returns_content_and_content_type(
        self,
        httpx_mock: HTTPXMock,
        ixp_service: IxpDesigntimeService,
    ) -> None:
        httpx_mock.add_response(
            content=b"\x89PNG\r\n", headers={"content-type": "image/png"}
        )

        content, content_type = ixp_service._download(
            ixp_service._endpoint(
                "/api/projects/{name}/documents/{doc}", name="p", doc="d"
            )
        )

        assert content == b"\x89PNG\r\n"
        assert content_type == "image/png"

    def test_download_falls_back_to_octet_stream(
        self,
        httpx_mock: HTTPXMock,
        ixp_service: IxpDesigntimeService,
    ) -> None:
        httpx_mock.add_response(content=b"bytes", headers={})

        _content, content_type = ixp_service._download(
            ixp_service._endpoint(
                "/api/projects/{name}/documents/{doc}", name="p", doc="d"
            )
        )

        assert content_type == "application/octet-stream"


class TestAsync:
    @pytest.mark.anyio
    async def test_get_async_builds_designtime_url(
        self,
        httpx_mock: HTTPXMock,
        ixp_service: IxpDesigntimeService,
    ) -> None:
        httpx_mock.add_response(json={"value": []})

        await ixp_service._get_async(ixp_service._endpoint("/api/projects"))

        request = httpx_mock.get_request()
        assert request is not None
        assert request.url.path == "/org/tenant/du_/api/designtimeapi/api/projects"
        assert request.url.params.get("api-version") == "1.0"

    @pytest.mark.anyio
    async def test_post_async_not_retried_on_transient_error(
        self,
        httpx_mock: HTTPXMock,
        ixp_service: IxpDesigntimeService,
    ) -> None:
        httpx_mock.add_response(status_code=502)

        with pytest.raises(EnrichedException) as exc_info:
            await ixp_service._post_async(
                ixp_service._endpoint("/api/projects"), body={"Name": "p"}
            )

        assert exc_info.value.status_code == 502
        assert len(httpx_mock.get_requests()) == 1
