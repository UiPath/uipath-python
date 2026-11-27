import json
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx._multipart import MultipartStream
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.documents import (
    ClassificationResult,
    DocumentsService,
    DocumentsServiceV2,
    ProjectType,
    StreamingFile,
)
from uipath.platform.documents._streaming_upload import (
    aiter_body,
    iter_body,
    multipart_layout,
)
from uipath.platform.errors import EnrichedException

DATA = b"%PDF-1.7 " + bytes(range(256)) * 40  # 10 KiB, every byte value
CHUNK = 4096


@pytest.fixture(params=[DocumentsService, DocumentsServiceV2], ids=["v1.1", "v2"])
def service(
    request: pytest.FixtureRequest,
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
) -> DocumentsService | DocumentsServiceV2:
    return request.param(config=config, execution_context=execution_context)


def api_version(service: DocumentsService | DocumentsServiceV2) -> str:
    return "2.0" if isinstance(service, DocumentsServiceV2) else "1.1"


def tag_route(service: DocumentsService | DocumentsServiceV2, tag: str) -> str:
    return f"tags/{tag}" if isinstance(service, DocumentsServiceV2) else tag


class Source:
    """Counts how often `open` is called, and whether each opened stream closed."""

    def __init__(self, data: bytes = DATA) -> None:
        self.data = data
        self.opened = 0
        self.closed = 0

    def sync(self) -> Iterator[bytes]:
        self.opened += 1
        try:
            for start in range(0, len(self.data), CHUNK):
                yield self.data[start : start + CHUNK]
        finally:
            self.closed += 1

    async def asynchronous(self) -> AsyncIterator[bytes]:
        self.opened += 1
        try:
            for start in range(0, len(self.data), CHUNK):
                yield self.data[start : start + CHUNK]
        finally:
            self.closed += 1


def streaming_file(open_: Any, size: int = len(DATA)) -> StreamingFile:
    return StreamingFile(
        name="appraisal.pdf", size=size, open=open_, content_type="application/pdf"
    )


async def call(
    service: DocumentsService | DocumentsServiceV2,
    method: str,
    mode: str,
    **kwargs: Any,
) -> Any:
    """Call `method`, or await `<method>_async`, so one test covers both."""
    if mode == "sync":
        return getattr(service, method)(**kwargs)
    return await getattr(service, f"{method}_async")(**kwargs)


def source_for(source: "Source", mode: str) -> Any:
    """The sync generator for the sync method, the async one for the async method."""
    return source.sync if mode == "sync" else source.asynchronous


def expected_files() -> dict[str, Any]:
    return {"File": ("appraisal.pdf", DATA, "application/pdf")}


def add_project_and_extraction(
    httpx_mock: HTTPXMock,
    service: DocumentsService | DocumentsServiceV2,
    root: str,
    project_id: str,
    document_id: str,
    operation_id: str,
) -> None:
    httpx_mock.add_response(
        url=f"{root}/du_/api/framework/projects?api-version={api_version(service)}&type=IXP",
        json={"projects": [{"id": project_id, "name": "LoanProject"}]},
    )
    httpx_mock.add_response(
        method="POST",
        url=f"{root}/du_/api/framework/projects/{project_id}/{tag_route(service, 'live')}/document-types/{UUID(int=0)}/extraction/start?api-version={api_version(service)}",
        match_json={"documentId": document_id},
        json={"operationId": operation_id},
    )


def digitization_url(
    service: DocumentsService | DocumentsServiceV2, root: str, project_id: str
) -> str:
    return f"{root}/du_/api/framework/projects/{project_id}/digitization/start?api-version={api_version(service)}"


class TestMultipartLayout:
    @pytest.mark.parametrize(
        "name",
        ["appraisal.pdf", 'loan "final".pdf', "back\\slash.pdf", "line\r\nbreak.pdf"],
    )
    def test_body_matches_what_httpx_writes(self, name: str):
        source = Source()
        file = StreamingFile(
            name=name, size=len(DATA), open=source.sync, content_type="application/pdf"
        )
        layout = multipart_layout(file, field_name="File")
        boundary = layout.content_type.split("boundary=")[1].encode()

        body = b"".join(iter_body(layout, file))

        httpx_body = b"".join(
            MultipartStream({}, {"File": (name, DATA, "application/pdf")}, boundary)
        )
        assert body == httpx_body
        assert layout.content_length == len(body)

    def test_each_layout_has_its_own_boundary(self):
        file = streaming_file(Source().sync)
        first = multipart_layout(file, "File")
        second = multipart_layout(file, "File")
        assert first.content_type != second.content_type

    async def test_async_body_accepts_a_sync_source(self):
        source = Source()
        file = streaming_file(source.sync)
        layout = multipart_layout(file, field_name="File")

        body = b"".join([chunk async for chunk in aiter_body(layout, file)])

        assert body == layout.head + DATA + layout.tail
        assert (source.opened, source.closed) == (1, 1)


class TestStartIxpExtractionWithFileStream:
    @pytest.mark.parametrize("mode", ["sync", "async", "async-with-sync-source"])
    async def test_uploads_the_stream_with_a_content_length(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService | DocumentsServiceV2,
        base_url: str,
        org: str,
        tenant: str,
        mode: str,
    ):
        root = f"{base_url}{org}{tenant}"
        project_id, document_id, operation_id = str(uuid4()), str(uuid4()), str(uuid4())
        add_project_and_extraction(
            httpx_mock, service, root, project_id, document_id, operation_id
        )
        httpx_mock.add_response(
            method="POST",
            url=digitization_url(service, root, project_id),
            match_headers={"X-UiPath-Internal-ConsumptionSourceType": "CodedAgents"},
            match_files=expected_files(),
            json={"documentId": document_id},
        )
        source = Source()

        if mode == "sync":
            response = service.start_ixp_extraction(
                project_name="LoanProject",
                tag="live",
                file_stream=streaming_file(source.sync),
            )
        else:
            open_ = source.asynchronous if mode == "async" else source.sync
            response = await service.start_ixp_extraction_async(
                project_name="LoanProject",
                tag="live",
                file_stream=streaming_file(open_),
            )

        assert response.document_id == document_id
        assert response.operation_id == operation_id
        assert (source.opened, source.closed) == (1, 1)
        upload = next(
            r for r in httpx_mock.get_requests() if r.url.path.endswith("/start")
        )
        assert "transfer-encoding" not in upload.headers
        assert int(upload.headers["content-length"]) == len(upload.content)

    @pytest.mark.parametrize("mode", ["sync", "async"])
    async def test_retry_reads_the_source_again_from_the_start(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService | DocumentsServiceV2,
        base_url: str,
        org: str,
        tenant: str,
        mode: str,
    ):
        root = f"{base_url}{org}{tenant}"
        project_id, document_id, operation_id = str(uuid4()), str(uuid4()), str(uuid4())
        add_project_and_extraction(
            httpx_mock, service, root, project_id, document_id, operation_id
        )
        url = digitization_url(service, root, project_id)
        httpx_mock.add_response(
            method="POST",
            url=url,
            match_files=expected_files(),
            status_code=503,
            headers={"retry-after": "0"},
        )
        httpx_mock.add_response(
            method="POST",
            url=url,
            match_files=expected_files(),
            json={"documentId": document_id},
        )
        source = Source()

        if mode == "sync":
            response = service.start_ixp_extraction(
                project_name="LoanProject",
                tag="live",
                file_stream=streaming_file(source.sync),
            )
        else:
            response = await service.start_ixp_extraction_async(
                project_name="LoanProject",
                tag="live",
                file_stream=streaming_file(source.asynchronous),
            )

        assert response.document_id == document_id
        assert (source.opened, source.closed) == (2, 2)

    @pytest.mark.parametrize("mode", ["sync", "async"])
    async def test_client_error_is_not_retried(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService | DocumentsServiceV2,
        base_url: str,
        org: str,
        tenant: str,
        mode: str,
    ):
        root = f"{base_url}{org}{tenant}"
        project_id = str(uuid4())
        httpx_mock.add_response(
            url=f"{root}/du_/api/framework/projects?api-version={api_version(service)}&type=IXP",
            json={"projects": [{"id": project_id, "name": "LoanProject"}]},
        )
        httpx_mock.add_response(
            method="POST",
            url=digitization_url(service, root, project_id),
            status_code=413,
        )
        source = Source()
        file_stream = streaming_file(source_for(source, mode))

        with pytest.raises(EnrichedException) as exc_info:
            await call(
                service,
                "start_ixp_extraction",
                mode,
                project_name="LoanProject",
                tag="live",
                file_stream=file_stream,
            )

        assert exc_info.value.status_code == 413
        assert (source.opened, source.closed) == (1, 1)

    @pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
    @pytest.mark.parametrize("mode", ["sync", "async"])
    @pytest.mark.parametrize(
        "declared, match",
        [(len(DATA) + 1, "but its source yielded"), (len(DATA) - 1, "more than")],
        ids=["too-few-bytes", "too-many-bytes"],
    )
    async def test_wrong_size_fails_without_retry(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService | DocumentsServiceV2,
        base_url: str,
        org: str,
        tenant: str,
        mode: str,
        declared: int,
        match: str,
    ):
        root = f"{base_url}{org}{tenant}"
        project_id = str(uuid4())
        httpx_mock.add_response(
            url=f"{root}/du_/api/framework/projects?api-version={api_version(service)}&type=IXP",
            json={"projects": [{"id": project_id, "name": "LoanProject"}]},
        )
        httpx_mock.add_response(
            method="POST",
            url=digitization_url(service, root, project_id),
            json={"documentId": str(uuid4())},
        )
        source = Source()
        file_stream = streaming_file(source_for(source, mode), size=declared)

        with pytest.raises(ValueError, match=match):
            await call(
                service,
                "start_ixp_extraction",
                mode,
                project_name="LoanProject",
                tag="live",
                file_stream=file_stream,
            )

        assert (source.opened, source.closed) == (1, 1)

    @pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
    async def test_sync_method_rejects_an_async_source(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService | DocumentsServiceV2,
        base_url: str,
        org: str,
        tenant: str,
    ):
        root = f"{base_url}{org}{tenant}"
        httpx_mock.add_response(
            url=f"{root}/du_/api/framework/projects?api-version={api_version(service)}&type=IXP",
            json={"projects": [{"id": str(uuid4()), "name": "LoanProject"}]},
        )
        file_stream = streaming_file(Source().asynchronous)

        with pytest.raises(TypeError, match="AsyncIterable|async source"):
            service.start_ixp_extraction(
                project_name="LoanProject",
                tag="live",
                file_stream=file_stream,
            )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    async def test_file_stream_cannot_be_combined_with_file(
        self,
        service: DocumentsService | DocumentsServiceV2,
        mode: str,
    ):
        file_stream = streaming_file(Source().sync)
        with pytest.raises(ValueError, match="Exactly one of"):
            await call(
                service,
                "start_ixp_extraction",
                mode,
                project_name="LoanProject",
                tag="live",
                file=b"x",
                file_stream=file_stream,
            )


PRETRAINED_PROJECT_ID = str(UUID(int=0))


def add_digitization(
    httpx_mock: HTTPXMock,
    service: DocumentsService | DocumentsServiceV2,
    root: str,
    document_id: str,
) -> None:
    project = f"{root}/du_/api/framework/projects/{PRETRAINED_PROJECT_ID}"
    httpx_mock.add_response(
        method="POST",
        url=f"{project}/digitization/start?api-version={api_version(service)}",
        match_files=expected_files(),
        json={"documentId": document_id},
    )
    httpx_mock.add_response(
        url=f"{project}/digitization/result/{document_id}?api-version={api_version(service)}",
        json={"status": "Succeeded", "result": {}},
    )


class TestClassifyAndExtractWithFileStream:
    @pytest.mark.parametrize("mode", ["sync", "async"])
    async def test_classify_uploads_the_stream(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService | DocumentsServiceV2,
        base_url: str,
        org: str,
        tenant: str,
        mode: str,
        classification_response: dict[str, Any],
    ):
        root = f"{base_url}{org}{tenant}"
        project = f"{root}/du_/api/framework/projects/{PRETRAINED_PROJECT_ID}"
        document_id, operation_id = str(uuid4()), str(uuid4())
        add_digitization(httpx_mock, service, root, document_id)
        httpx_mock.add_response(
            method="POST",
            url=f"{project}/classifiers/ml-classification/classification/start?api-version={api_version(service)}",
            match_json={"documentId": document_id},
            json={"operationId": operation_id},
        )
        httpx_mock.add_response(
            url=f"{project}/classifiers/ml-classification/classification/result/{operation_id}?api-version={api_version(service)}",
            json={"status": "Succeeded", "result": classification_response},
        )
        source = Source()

        if mode == "sync":
            results = service.classify(
                project_type=ProjectType.PRETRAINED,
                file_stream=streaming_file(source.sync),
            )
        else:
            results = await service.classify_async(
                project_type=ProjectType.PRETRAINED,
                file_stream=streaming_file(source.asynchronous),
            )

        assert (
            results[0].document_id
            == classification_response["classificationResults"][0]["DocumentId"]
        )
        assert (source.opened, source.closed) == (1, 1)

    @pytest.mark.parametrize("mode", ["sync", "async"])
    async def test_extract_uploads_the_stream(
        self,
        httpx_mock: HTTPXMock,
        service: DocumentsService | DocumentsServiceV2,
        base_url: str,
        org: str,
        tenant: str,
        mode: str,
        documents_tests_data_path: Path,
    ):
        modern_extraction_response = json.loads(
            (documents_tests_data_path / "modern_extraction_response.json").read_text()
        )
        root = f"{base_url}{org}{tenant}"
        project = f"{root}/du_/api/framework/projects/{PRETRAINED_PROJECT_ID}"
        document_id, operation_id = str(uuid4()), str(uuid4())
        add_digitization(httpx_mock, service, root, document_id)
        httpx_mock.add_response(
            url=f"{project}/document-types?api-version={api_version(service)}",
            json={"documentTypes": [{"id": "invoices", "name": "Invoice"}]},
        )
        httpx_mock.add_response(
            method="POST",
            url=f"{project}/extractors/invoices/extraction/start?api-version={api_version(service)}",
            match_json={"documentId": document_id},
            json={"operationId": operation_id},
        )
        httpx_mock.add_response(
            url=f"{project}/extractors/invoices/extraction/result/{operation_id}?api-version={api_version(service)}",
            json={"status": "Succeeded", "result": modern_extraction_response},
        )
        source = Source()

        if mode == "sync":
            response = service.extract(
                project_type=ProjectType.PRETRAINED,
                document_type_name="Invoice",
                file_stream=streaming_file(source.sync),
            )
        else:
            response = await service.extract_async(
                project_type=ProjectType.PRETRAINED,
                document_type_name="Invoice",
                file_stream=streaming_file(source.asynchronous),
            )

        assert response.extractor_id == "invoices"
        assert response.document_type_id == "invoices"
        assert (source.opened, source.closed) == (1, 1)

    @pytest.mark.parametrize("mode", ["sync", "async"])
    async def test_classify_rejects_file_stream_with_file_path(
        self,
        service: DocumentsService | DocumentsServiceV2,
        mode: str,
    ):
        file_stream = streaming_file(Source().sync)
        with pytest.raises(
            ValueError,
            match="Exactly one of `file, file_path, file_stream` must be provided",
        ):
            await call(
                service,
                "classify",
                mode,
                project_type=ProjectType.PRETRAINED,
                file_path="document.pdf",
                file_stream=file_stream,
            )

    @pytest.mark.parametrize("mode", ["sync", "async"])
    async def test_extract_rejects_file_stream_with_a_classification_result(
        self,
        service: DocumentsService | DocumentsServiceV2,
        mode: str,
        classification_response: dict[str, Any],
    ):
        result = ClassificationResult.model_validate(
            {
                **classification_response["classificationResults"][0],
                "ProjectId": PRETRAINED_PROJECT_ID,
                "ProjectType": ProjectType.PRETRAINED.value,
                "ClassifierId": "ml-classification",
                "Tag": None,
            }
        )
        file_stream = streaming_file(Source().sync)
        # Same rule as for `file`: a document and a classification result exclude
        # each other.
        args: dict[str, Any] = {
            "classification_result": result,
            "project_type": ProjectType.PRETRAINED,
            "document_type_name": "Invoice",
            "file_stream": file_stream,
        }
        with pytest.raises(
            ValueError, match="`classification_result` must not be provided"
        ):
            await call(service, "extract", mode, **args)


class TestStreamingFileModel:
    def test_rejects_a_negative_size(self):
        with pytest.raises(ValueError):
            StreamingFile(name="a.pdf", size=-1, open=lambda: iter([b""]))

    def test_rejects_an_empty_name(self):
        with pytest.raises(ValueError):
            StreamingFile(name="", size=0, open=lambda: iter([b""]))

    def test_defaults_to_octet_stream(self):
        file = StreamingFile(name="a.pdf", size=0, open=lambda: iter([]))
        assert file.content_type == "application/octet-stream"
