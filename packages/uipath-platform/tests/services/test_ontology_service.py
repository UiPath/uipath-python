import hashlib
import json
from typing import Any

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPath, UiPathApiConfig, UiPathExecutionContext
from uipath.platform.common._bindings import (
    GenericResourceOverwrite,
    ResourceOverwriteParser,
    _resource_overwrites,
)
from uipath.platform.constants import (
    HEADER_FOLDER_KEY,
    HEADER_INTERNAL_ACCOUNT_ID,
    HEADER_INTERNAL_TENANT_ID,
    HEADER_USER_AGENT,
)
from uipath.platform.ontology import (
    ArtifactDownload,
    OntologyArtifact,
    OntologyArtifactIntegrityError,
    OntologyService,
    SqlResult,
)
from uipath.platform.ontology._ontology_service import _checked_statement

ONTOLOGY_ID = "c0d9f850-ba58-443e-8c54-0bc4bd68f202"
FOLDER_KEY = "f65ca4a9-5c89-49f5-a144-78e510f6ea6c"
SCHEMA = b"Prefix(:=<https://ontology.uipath.com/nxorders#>)\nOntology(<x>)\n"


def _sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _manifest_entry(
    file_name: str, artifact_type: str, content: bytes
) -> dict[str, Any]:
    return {
        "fileName": file_name,
        "type": artifact_type,
        "mediaType": "text/owl-functional",
        "sizeBytes": len(content),
        "checksum": _sha(content),
        "createdBy": "someone",
        "createTime": "2026-11-18T06:00:00Z",
    }


@pytest.fixture
def service(
    config: UiPathApiConfig, execution_context: UiPathExecutionContext
) -> OntologyService:
    return OntologyService(config=config, execution_context=execution_context)


@pytest.fixture
def api(base_url: str, org: str, tenant: str) -> str:
    return f"{base_url}{org}{tenant}/ontology_/api/v1/ontology"


class TestOntologyService:
    def test_exposed_on_the_client(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UIPATH_URL", "https://test.uipath.com/org/tenant")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "secret")
        sdk = UiPath()
        assert isinstance(sdk.ontology, OntologyService)

    async def test_get_reads_details_by_id(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}",
            json={
                "id": ONTOLOGY_ID,
                "name": "nxorders",
                "displayName": "Orders (fresh e2e)",
                "folderId": FOLDER_KEY,
                "state": "DEPLOYED",
                "somethingNew": True,
            },
        )

        details = await service.get_async(ONTOLOGY_ID)

        assert details.name == "nxorders"
        assert details.display_name == "Orders (fresh e2e)"
        assert details.folder_id == FOLDER_KEY
        assert details.is_deployed
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "GET"
        assert HEADER_USER_AGENT in request.headers
        assert HEADER_FOLDER_KEY not in request.headers

    async def test_name_lookup_carries_the_folder_header(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{api}/nxorders",
            json={"id": ONTOLOGY_ID, "name": "nxorders", "state": "DRAFT"},
        )

        details = await service.get_async("nxorders", folder_key=FOLDER_KEY)

        assert not details.is_deployed
        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY

    def test_sync_get(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}", json={"id": ONTOLOGY_ID, "name": "nxorders"}
        )
        assert service.get(ONTOLOGY_ID).id == ONTOLOGY_ID

    async def test_ids_and_file_names_are_path_encoded(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{api}/a%2F..%2Fb/artifact/x%2F..%2Fy.ofn", content=b"x"
        )

        content = await service.get_artifact_async("a/../b", "x/../y.ofn")

        assert content.content == b"x"

    @pytest.mark.parametrize("bad", ["", "   "])
    async def test_blank_id_is_refused_before_any_request(
        self, service: OntologyService, bad: str
    ) -> None:
        with pytest.raises(ValueError, match="ontology_id"):
            await service.get_async(bad)

    async def test_list_artifacts_returns_the_manifest(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/artifact",
            json=[
                _manifest_entry("nxorders.ofn", "schema", SCHEMA),
                _manifest_entry("nxorders-summary.json", "summary", b"{}"),
            ],
        )

        manifest = await service.list_artifacts_async(ONTOLOGY_ID)

        assert [a.file_name for a in manifest] == [
            "nxorders.ofn",
            "nxorders-summary.json",
        ]
        assert manifest[0].size_bytes == len(SCHEMA)
        assert manifest[0].checksum == _sha(SCHEMA)
        assert manifest[0].created_by == "someone"

    async def test_list_artifacts_filters_by_type(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/artifact?type=schema",
            json=[_manifest_entry("nxorders.ofn", "schema", SCHEMA)],
        )

        manifest = await service.list_artifacts_async(ONTOLOGY_ID, "schema")

        assert len(manifest) == 1
        request = httpx_mock.get_request()
        assert request is not None
        assert request.url.params["type"] == "schema"

    async def test_get_artifact_returns_bytes_media_type_and_etag(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/artifact/nxorders.ofn",
            content=SCHEMA,
            headers={
                "content-type": "text/owl-functional",
                "etag": f'"{_sha(SCHEMA)}"',
            },
        )

        content = await service.get_artifact_async(ONTOLOGY_ID, "nxorders.ofn")

        assert content.content == SCHEMA
        assert content.text.startswith("Prefix(")
        assert content.media_type == "text/owl-functional"
        assert content.etag == f'"{_sha(SCHEMA)}"'
        assert content.sha256() == _sha(SCHEMA)

    async def test_get_artifact_verifies_against_the_manifest(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        expected = OntologyArtifact.model_validate(
            _manifest_entry("nxorders.ofn", "schema", SCHEMA)
        )
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/artifact/nxorders.ofn", content=SCHEMA
        )

        content = await service.get_artifact_async(
            ONTOLOGY_ID, "nxorders.ofn", expected=expected
        )

        assert content.type == "schema"

    async def test_get_artifact_refuses_a_checksum_mismatch(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        tampered = SCHEMA[:-1] + b"!"
        expected = OntologyArtifact.model_validate(
            _manifest_entry("nxorders.ofn", "schema", SCHEMA)
        )
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/artifact/nxorders.ofn", content=tampered
        )

        with pytest.raises(OntologyArtifactIntegrityError, match="checksum"):
            await service.get_artifact_async(
                ONTOLOGY_ID, "nxorders.ofn", expected=expected
            )

    async def test_get_artifact_refuses_a_size_mismatch(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        expected = OntologyArtifact.model_validate(
            _manifest_entry("nxorders.ofn", "schema", SCHEMA)
        )
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/artifact/nxorders.ofn", content=SCHEMA + b"\n"
        )

        with pytest.raises(OntologyArtifactIntegrityError, match="bytes"):
            await service.get_artifact_async(
                ONTOLOGY_ID, "nxorders.ofn", expected=expected
            )

    async def test_get_artifact_by_type_reads_the_schema_in_one_request(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/artifact/type/schema",
            content=SCHEMA,
            headers={
                "content-type": "text/owl-functional",
                "etag": f'"{_sha(SCHEMA)}"',
                "content-disposition": (
                    "attachment; filename=\"nxorders.ofn\"; filename*=UTF-8''nxorders.ofn"
                ),
            },
        )

        content = await service.get_artifact_by_type_async(ONTOLOGY_ID, "schema")

        assert content.content == SCHEMA
        assert content.file_name == "nxorders.ofn"
        assert content.type == "schema"
        assert content.media_type == "text/owl-functional"
        assert len(httpx_mock.get_requests()) == 1

    def test_sync_get_artifact_by_type(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/artifact/type/schema",
            content=SCHEMA,
            headers={"etag": f'"{_sha(SCHEMA)}"'},
        )

        content = service.get_artifact_by_type(ONTOLOGY_ID, "schema")

        assert content.text == SCHEMA.decode()
        assert content.file_name == "schema"

    async def test_get_artifact_by_type_refuses_content_that_misses_its_etag(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/artifact/type/schema",
            content=SCHEMA,
            headers={"etag": '"0000"'},
        )

        with pytest.raises(OntologyArtifactIntegrityError, match="ETag"):
            await service.get_artifact_by_type_async(ONTOLOGY_ID, "schema")

    async def test_download_artifacts_verifies_each_file_and_skips_oversize(
        self,
        httpx_mock: HTTPXMock,
        service: OntologyService,
        api: str,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        huge = b"x" * 300
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/artifact?type=schema",
            json=[
                _manifest_entry("nxorders.ofn", "schema", SCHEMA),
                _manifest_entry("huge.ofn", "schema", huge),
            ],
        )
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/artifact/nxorders.ofn", content=SCHEMA
        )

        with caplog.at_level("WARNING"):
            result = await service.download_artifacts_async(
                ONTOLOGY_ID, "schema", max_bytes=200
            )

        assert isinstance(result, ArtifactDownload)
        assert [c.file_name for c in result.files] == ["nxorders.ofn"]
        assert result.files[0].type == "schema"
        assert [(s.file_name, s.size_bytes) for s in result.skipped] == [
            ("huge.ofn", 300)
        ]
        assert "200 byte cap" in result.skipped[0].reason
        assert "huge.ofn" in caplog.text
        # the oversize file was never requested
        assert len(httpx_mock.get_requests()) == 2

    async def test_download_artifacts_keeps_manifest_order_across_files(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        files = {f"part{i}.ofn": f"Ontology(<p{i}>)".encode() for i in range(6)}
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/artifact?type=schema",
            json=[_manifest_entry(n, "schema", c) for n, c in files.items()],
        )
        for name, content in files.items():
            httpx_mock.add_response(
                url=f"{api}/{ONTOLOGY_ID}/artifact/{name}", content=content
            )

        result = await service.download_artifacts_async(ONTOLOGY_ID, "schema")

        assert [c.file_name for c in result.files] == list(files)
        assert [c.content for c in result.files] == list(files.values())
        assert result.skipped == []

    def test_sync_download_artifacts_reports_skipped(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/artifact",
            json=[
                _manifest_entry("nxorders.ofn", "schema", SCHEMA),
                _manifest_entry("mapping.yml", "mapping", b"y" * 500),
            ],
        )
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/artifact/nxorders.ofn", content=SCHEMA
        )

        result = service.download_artifacts(ONTOLOGY_ID, max_bytes=200)

        assert [c.file_name for c in result.files] == ["nxorders.ofn"]
        assert [s.type for s in result.skipped] == ["mapping"]

    async def test_get_graph_returns_the_raw_view(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        graph = {"objects": [{"name": "SalesOrder"}], "relationships": []}
        httpx_mock.add_response(url=f"{api}/{ONTOLOGY_ID}/graph", json=graph)

        assert await service.get_graph_async(ONTOLOGY_ID) == graph

    async def test_execute_sql_posts_statement_and_params(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/sql",
            json={
                "columns": [{"name": "name", "type": "xsd:string"}],
                "rows": [{"name": "Ana"}, {"name": "Bo"}],
                "rowCount": 2,
            },
        )

        result = await service.execute_sql_async(
            ONTOLOGY_ID,
            "SELECT name FROM Supplier WHERE country = :c",
            {"c": "RO"},
        )

        assert isinstance(result, SqlResult)
        assert result.row_count == 2
        assert result.column_names == ["name"]
        assert result.rows[1]["name"] == "Bo"
        request = httpx_mock.get_request()
        assert request is not None
        assert request.method == "POST"
        body = json.loads(request.content)
        assert body["params"] == {"c": "RO"}
        assert body["statement"] == "SELECT name FROM Supplier WHERE country = :c"

    async def test_execute_sql_without_declared_columns(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{api}/{ONTOLOGY_ID}/sql",
            json={"rows": [{"anything": "at all"}], "rowCount": 1},
        )

        result = await service.execute_sql_async(ONTOLOGY_ID, "SELECT 1")

        assert result.column_names == ["anything"]

    async def test_local_override_redirects_and_injects_routing_headers(
        self,
        httpx_mock: HTTPXMock,
        service: OntologyService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("UIPATH_SERVICE_URL_ONTOLOGY", "http://localhost:5002")
        monkeypatch.setenv("UIPATH_TENANT_ID", "tenant-id")
        monkeypatch.setenv("UIPATH_ORGANIZATION_ID", "org-id")
        httpx_mock.add_response(
            url=f"http://localhost:5002/api/v1/ontology/{ONTOLOGY_ID}",
            json={"id": ONTOLOGY_ID, "name": "nxorders"},
        )

        await service.get_async(ONTOLOGY_ID)

        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_INTERNAL_TENANT_ID] == "tenant-id"
        assert request.headers[HEADER_INTERNAL_ACCOUNT_ID] == "org-id"

    async def test_an_ontology_binding_repoints_the_call(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        overwrite = ResourceOverwriteParser.parse(
            f"ontology.{ONTOLOGY_ID}",
            {"name": "nxorders-prod", "folderPath": "Finance/Prod"},
        )
        assert isinstance(overwrite, GenericResourceOverwrite)
        httpx_mock.add_response(
            url=f"{api}/nxorders-prod",
            json={"id": "other", "name": "nxorders-prod", "state": "DEPLOYED"},
        )
        token = _resource_overwrites.set({f"ontology.{ONTOLOGY_ID}": overwrite})
        try:
            details = await service.get_async(ONTOLOGY_ID)
        finally:
            _resource_overwrites.reset(token)

        assert details.name == "nxorders-prod"
        request = httpx_mock.get_request()
        assert request is not None
        assert "x-uipath-folderpath" in {k.lower() for k in request.headers.keys()}

    async def test_a_binding_folder_key_goes_as_the_key_not_a_path(
        self, httpx_mock: HTTPXMock, service: OntologyService, api: str
    ) -> None:
        # The Agents packager writes the ontology's folder key into folderPath.
        overwrite = ResourceOverwriteParser.parse(
            f"ontology.{ONTOLOGY_ID}",
            {"name": "nxorders-prod", "folderPath": FOLDER_KEY},
        )
        httpx_mock.add_response(
            url=f"{api}/nxorders-prod",
            json={"id": "other", "name": "nxorders-prod", "state": "DEPLOYED"},
        )
        token = _resource_overwrites.set({f"ontology.{ONTOLOGY_ID}": overwrite})
        try:
            await service.get_async(ONTOLOGY_ID)
        finally:
            _resource_overwrites.reset(token)

        request = httpx_mock.get_request()
        assert request is not None
        assert request.headers[HEADER_FOLDER_KEY] == FOLDER_KEY
        assert "x-uipath-folderpath" not in {k.lower() for k in request.headers.keys()}


class TestCheckedStatement:
    def test_leaves_paging_words_and_comments_alone(self) -> None:
        statement = "SELECT n FROM Supplier WHERE n < :limit ORDER BY n -- page"
        assert _checked_statement(statement + "\n") == statement

    def test_drops_a_trailing_semicolon(self) -> None:
        assert _checked_statement("SELECT 1;  ") == "SELECT 1"

    def test_rejects_a_blank_statement(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            _checked_statement("  ")
