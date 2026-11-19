import base64
import json
from typing import Any, Dict

import httpx
import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.common._bindings import (
    ConnectionResourceOverwrite,
    _resource_overwrites,
)
from uipath.platform.constants import HEADER_FOLDER_KEY, HEADER_USER_AGENT
from uipath.platform.integration_service import (
    ExecuteActivityResult,
    ExecuteFile,
    ExecuteHttpResult,
    ExecuteResult,
    IntegrationService,
)
from uipath.platform.integration_service import execution as ex

CONNECTION_ID = "conn-123"


@pytest.fixture
def service(
    config: UiPathApiConfig, execution_context: UiPathExecutionContext
) -> IntegrationService:
    return IntegrationService(config=config, execution_context=execution_context)


@pytest.fixture
def instance_url(base_url: str, org: str, tenant: str) -> str:
    return f"{base_url}{org}{tenant}/elements_/v3/element/instances/{CONNECTION_ID}"


@pytest.fixture
def v4_url(base_url: str, org: str, tenant: str) -> str:
    return f"{base_url}{org}{tenant}/elements_/v4/execute"


def page_token(provider_next_page: str = "2") -> str:
    raw = json.dumps({"providerNextPage": provider_next_page}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def paging_headers(has_more: bool = True, token: str | None = None) -> Dict[str, str]:
    return {
        "elements-has-more": "true" if has_more else "false",
        "elements-next-page-token": token or page_token(),
    }


def sent(httpx_mock: HTTPXMock, index: int = -1) -> httpx.Request:
    return httpx_mock.get_requests()[index]


class TestBodyPaths:
    def test_body_without_paths_is_untouched(self) -> None:
        body = {"subject": "x", "nested": {"a.b": 1}}
        assert ex.expand_body_paths(body) is body

    def test_dotted_key_becomes_nested(self) -> None:
        assert ex.expand_body_paths(
            {"fields.summary": "x", "fields.project.key": "P", "plain": 1}
        ) == {"fields": {"summary": "x", "project": {"key": "P"}}, "plain": 1}

    def test_indexed_segment(self) -> None:
        assert ex.expand_body_paths({"items[1].name": "b", "tags[0]": "t"}) == {
            "items": [{}, {"name": "b"}],
            "tags": ["t"],
        }

    def test_wildcard_applies_to_every_item(self) -> None:
        assert ex.expand_body_paths(
            {"items[0].id": 1, "items[1].id": 2, "items[*].kind": "k"}
        ) == {"items": [{"id": 1, "kind": "k"}, {"id": 2, "kind": "k"}]}

    def test_wildcard_with_list_value_replaces_list(self) -> None:
        assert ex.expand_body_paths({"items[*]": [1, 2]}) == {"items": [1, 2]}

    def test_wildcard_with_dict_value_merges(self) -> None:
        assert ex.expand_body_paths({"items[0].a": 1, "items[*]": {"b": {"c": 2}}}) == {
            "items": [{"a": 1, "b": {"c": 2}}]
        }


class TestUrlInputs:
    def test_encodes_only_listed_url_values(self) -> None:
        query = {"link": "https://a.com/x?y=1", "other": "https://b.com", "q": "text"}
        encoded = ex.encode_url_inputs(query, ["Link[*]", "q"])
        assert encoded == {
            "link": base64.b64encode(b"https://a.com/x?y=1").decode(),
            "other": "https://b.com",
            "q": "text",
        }
        assert query["link"] == "https://a.com/x?y=1"

    def test_percent_encoded_url_is_recognised(self) -> None:
        assert ex.looks_like_url("https%3A%2F%2Fa.com%2Fx")
        assert not ex.looks_like_url("ftp://a.com")
        assert not ex.looks_like_url("just text")

    def test_paging_parameters_are_never_encoded(self) -> None:
        query = {"nextPage": "https://a.com"}
        assert ex.encode_url_inputs(query, ["nextPage"]) is query

    def test_no_fields_returns_same_query(self) -> None:
        query = {"a": "https://a.com"}
        assert ex.encode_url_inputs(query, None) is query


class TestResponseContent:
    @pytest.mark.parametrize(
        "headers,expected",
        [
            ({"content-type": "application/pdf"}, True),
            ({"content-type": "image/png"}, True),
            ({"Content-Type": "application/octet-stream"}, True),
            ({"content-type": "application/json"}, False),
            (
                {
                    "content-type": "text/csv",
                    "content-disposition": "attachment; filename=a.csv",
                },
                False,
            ),
            ({"content-type": "application/vnd.api+json"}, False),
            ({"content-type": "application/vnd.ms-excel"}, True),
            ({"content-type": "image/svg+xml"}, True),
            (
                {
                    "content-type": "text/html",
                    "content-disposition": "attachment; filename=a.html",
                },
                True,
            ),
            ({}, False),
        ],
    )
    def test_is_file_response(self, headers: Dict[str, str], expected: bool) -> None:
        assert ex.is_file_response(headers) is expected

    def test_to_result_parses_json_and_keeps_text(self) -> None:
        assert ex.to_result(httpx.Response(200, json={"a": 1})).body == {"a": 1}
        assert ex.to_result(httpx.Response(200, text="plain")).body == "plain"
        assert ex.to_result(httpx.Response(204)).body == ""

    def test_as_file_applies_to_success_only(self) -> None:
        assert ex.to_result(httpx.Response(200, json={"a": 1}), True).body == b'{"a":1}'
        assert ex.to_result(httpx.Response(404, json={"a": 1}), True).body == {"a": 1}


class TestPagination:
    def test_resolve_max_records(self) -> None:
        assert ex.resolve_max_records(None, "m") is None
        assert ex.resolve_max_records(-1, "m") == float("inf")
        assert ex.resolve_max_records(5, "m") == 5
        for bad in (0, -2, 1.5, True):
            with pytest.raises(ValueError, match="max_records"):
                ex.resolve_max_records(bad, "m")  # type: ignore[arg-type]

    def test_extract_page(self) -> None:
        token = page_token()
        page = ex.extract_page(paging_headers(token=token), [1])
        assert page is not None
        assert page.has_more is True
        assert page.next_page_token == token

    def test_extract_page_none_cases(self) -> None:
        assert ex.extract_page({}, [1]) is None
        assert ex.extract_page(paging_headers(), {"not": "a list"}) is None
        assert ex.extract_page(paging_headers(token=page_token("done")), [1]) is None

    def test_unreadable_token_is_still_a_token(self) -> None:
        page = ex.extract_page(paging_headers(token="!!not-base64!!"), [1])
        assert page is not None and page.next_page_token == "!!not-base64!!"


class TestV4Helpers:
    @pytest.mark.parametrize(
        "version,expected",
        [
            ("4.0.0", True),
            ("v4", True),
            ("12.1", True),
            (" 4.2 ", True),
            ("3.9.9", False),
            ("", False),
            (None, False),
            ("latest", False),
        ],
    )
    def test_uses_v4_engine(self, version: str | None, expected: bool) -> None:
        assert ex.uses_v4_engine(version) is expected

    def test_manifest_for_json_body(self) -> None:
        manifest = ex.build_v4_manifest(
            connection_id="c",
            connector_key="uipath-x",
            method="POST",
            url="https://api.example.com/t?a=1",
            headers={"X-A": "1"},
            query_params={"b": "2 3"},
            body={"k": "v"},
            file=None,
        )
        assert manifest == {
            "outboundRequestConfig": {
                "method": "POST",
                "url": "https://api.example.com/t?a=1&b=2+3",
                "headers": [
                    {"name": "X-A", "value": "1"},
                    {"name": "Content-Type", "value": "application/json"},
                ],
                "body": '{"k": "v"}',
            },
            "context": {"connectionId": "c", "connectorKey": "uipath-x"},
        }

    def test_manifest_keeps_caller_content_type_and_string_body(self) -> None:
        manifest = ex.build_v4_manifest(
            connection_id="c",
            connector_key=None,
            method="POST",
            url="https://x",
            headers={"content-type": "text/plain"},
            query_params=None,
            body="raw",
            file=None,
        )
        assert manifest["outboundRequestConfig"] == {
            "method": "POST",
            "url": "https://x",
            "headers": [{"name": "content-type", "value": "text/plain"}],
            "body": "raw",
        }
        assert manifest["context"] == {"connectionId": "c"}

    def test_unwrap_base64_body(self) -> None:
        result = ex.unwrap_v4_response(
            ExecuteResult(
                ok=True,
                status=200,
                body={
                    "status": 200,
                    "headers": {"set-cookie": ["a", "b"], "x": 1, "n": None},
                    "body": base64.b64encode(b"\x00\x01").decode(),
                    "bodyEncoding": "base64",
                },
            )
        )
        assert result.ok and not result.is_vendor_error
        assert result.body == b"\x00\x01"
        assert result.headers == {"set-cookie": "a, b", "x": "1"}

    def test_unwrap_engine_failure_is_not_a_vendor_error(self) -> None:
        result = ex.unwrap_v4_response(
            ExecuteResult(ok=False, status=400, body={"message": "relative url"})
        )
        assert result.status == 400 and not result.ok and not result.is_vendor_error

    def test_unwrap_two_part_answer(self) -> None:
        payload = b"%PDF\r\n--b1\r\nbinary\x00"
        document = (
            b"--b1\r\nContent-Type: application/json\r\n\r\n"
            + json.dumps({"status": 404, "headers": {"a": "b"}}).encode()
            + b"\r\n--b1\r\nContent-Type: application/pdf\r\n\r\n"
            + payload
            + b"\r\n--b1--\r\n"
        )
        result = ex.unwrap_v4_response(
            ExecuteResult(
                ok=True,
                status=200,
                body=document,
                headers={"content-type": 'multipart/mixed; boundary="b1"'},
            )
        )
        assert result.status == 404 and result.is_vendor_error
        assert result.body == payload
        assert result.headers == {"a": "b"}

    def test_truncated_two_part_answer_is_refused(self) -> None:
        document = b'--b1\r\n\r\n{"status": 200}\r\n--b1\r\n\r\npartial'
        with pytest.raises(ValueError, match="incomplete file response"):
            ex.unwrap_v4_response(
                ExecuteResult(
                    ok=True,
                    status=200,
                    body=document,
                    headers={"content-type": "multipart/mixed; boundary=b1"},
                )
            )


class TestProxyResponse:
    def test_vendor_response_is_unwrapped(self) -> None:
        result = ex.unwrap_proxy_response(
            ExecuteResult(
                ok=True,
                status=200,
                body={
                    "code": 404,
                    "statusText": "Not Found",
                    "headers": {"x": "y"},
                    "rawStringBody": "nope",
                },
            )
        )
        assert result.model_dump() == {
            "ok": False,
            "status": 404,
            "status_text": "Not Found",
            "body": "nope",
            "headers": {"x": "y"},
            "is_vendor_error": True,
        }

    def test_parsed_body_wins(self) -> None:
        result = ex.unwrap_proxy_response(
            ExecuteResult(
                ok=True,
                status=200,
                body={"code": 200, "body": {"a": 1}, "rawStringBody": '{"a":1}'},
            )
        )
        assert result.ok and result.body == {"a": 1} and not result.is_vendor_error

    @pytest.mark.parametrize(
        "raw",
        [
            ExecuteResult(ok=False, status=401, body={"code": 200}),
            ExecuteResult(ok=True, status=200, body={"no": "code"}),
            ExecuteResult(ok=True, status=200, body="text"),
        ],
    )
    def test_integration_service_response_is_returned_as_is(
        self, raw: ExecuteResult
    ) -> None:
        result = ex.unwrap_proxy_response(raw)
        assert result.status == raw.status and result.body == raw.body
        assert result.is_vendor_error is False


class TestExecuteActivity:
    def test_get(
        self,
        httpx_mock: HTTPXMock,
        service: IntegrationService,
        instance_url: str,
        version: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{instance_url}/tickets?limit=10", json=[{"id": 1}]
        )

        result = service.execute_activity(
            CONNECTION_ID, "tickets", query_params={"limit": "10"}
        )

        assert isinstance(result, ExecuteActivityResult)
        assert result.ok and result.status == 200
        assert result.body == [{"id": 1}]
        assert result.page is None
        request = sent(httpx_mock)
        assert request.method == "GET"
        assert request.content == b""
        assert request.headers["x-uipath-originator"] == "uipath-python"
        assert HEADER_FOLDER_KEY not in request.headers
        assert request.headers[HEADER_USER_AGENT].endswith(
            f"IntegrationService.execute/{version}"
        )

    def test_non_2xx_is_returned_not_raised(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{instance_url}/tickets", status_code=404, json={"message": "no"}
        )

        result = service.execute_activity(CONNECTION_ID, "tickets")

        assert not result.ok
        assert result.status == 404
        assert result.body == {"message": "no"}
        assert len(httpx_mock.get_requests()) == 1

    def test_server_error_is_not_retried_by_default(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(url=f"{instance_url}/tickets", status_code=503)

        assert service.execute_activity(CONNECTION_ID, "tickets").status == 503
        assert len(httpx_mock.get_requests()) == 1

    def test_post_expands_body_paths(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(url=f"{instance_url}/issues", json={"id": "1"})

        service.execute_activity(
            CONNECTION_ID,
            "issues",
            "post",
            body={"fields.summary": "x", "key": "K"},
            folder_key="folder-1",
        )

        request = sent(httpx_mock)
        assert request.method == "POST"
        assert json.loads(request.content) == {"fields": {"summary": "x"}, "key": "K"}
        assert request.headers["content-type"] == "application/json"
        assert request.headers[HEADER_FOLDER_KEY] == "folder-1"

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH"])
    def test_write_without_body_sends_empty_object(
        self,
        httpx_mock: HTTPXMock,
        service: IntegrationService,
        instance_url: str,
        method: str,
    ) -> None:
        httpx_mock.add_response(url=f"{instance_url}/tickets", json={})

        service.execute_activity(CONNECTION_ID, "tickets", method)

        assert json.loads(sent(httpx_mock).content) == {}

    def test_delete_carries_no_body(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(url=f"{instance_url}/tickets/1", status_code=204)

        result = service.execute_activity(
            CONNECTION_ID, "tickets/1", "DELETE", body={"ignored": True}
        )

        assert result.ok and result.body == ""
        assert sent(httpx_mock).content == b""

    def test_object_name_segments_are_encoded(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(json={})

        service.execute_activity(CONNECTION_ID, "curated_get/A B#1")

        assert (
            sent(httpx_mock)
            .url.raw_path.decode()
            .endswith(f"/instances/{CONNECTION_ID}/curated_get/A%20B%231")
        )

    def test_file_upload_is_multipart(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(url=f"{instance_url}/files", json={"id": "f"})

        service.execute_activity(
            CONNECTION_ID,
            "files",
            "POST",
            body={"title": "Report"},
            files=[
                ExecuteFile(
                    name="file",
                    content=b"%PDF-1",
                    file_name="r.pdf",
                    content_type="application/pdf",
                ),
                ExecuteFile(name="extra", content=b"abc"),
            ],
        )

        request = sent(httpx_mock)
        assert request.headers["content-type"].startswith("multipart/form-data")
        content = request.content
        assert b'name="body"\r\n\r\n{"title": "Report"}' in content
        assert b'name="file"; filename="r.pdf"' in content
        assert b"Content-Type: application/pdf\r\n\r\n%PDF-1" in content
        assert b'name="extra"; filename="file"' in content
        assert b"Content-Type: application/octet-stream\r\n\r\nabc" in content
        assert content.index(b'name="body"') < content.index(b'name="file"')

    def test_file_upload_without_body_has_no_body_part(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(url=f"{instance_url}/files", json={})

        service.execute_activity(
            CONNECTION_ID,
            "files",
            "POST",
            files=[ExecuteFile(name="file", content=b"abc")],
            body_part_name="meta",
        )

        content = sent(httpx_mock).content
        assert b'name="meta"' not in content and b'name="body"' not in content

    def test_file_download_detected_from_headers(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{instance_url}/files/1/content",
            content=b"\x89PNG",
            headers={"content-type": "image/png"},
        )

        result = service.execute_activity(CONNECTION_ID, "files/1/content")

        assert result.body == b"\x89PNG"

    def test_file_response_forces_bytes(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(url=f"{instance_url}/export", text="a,b")

        result = service.execute_activity(CONNECTION_ID, "export", file_response=True)

        assert result.body == b"a,b"

    def test_url_input_fields_are_base64_encoded(
        self, httpx_mock: HTTPXMock, service: IntegrationService
    ) -> None:
        httpx_mock.add_response(json=[])

        service.execute_activity(
            CONNECTION_ID,
            "pages",
            query_params={"url": "https://a.com/x", "q": "t"},
            url_input_fields=["url"],
        )

        params = sent(httpx_mock).url.params
        assert params["url"] == base64.b64encode(b"https://a.com/x").decode()
        assert params["q"] == "t"

    def test_single_page_reports_paging_state(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        token = page_token()
        httpx_mock.add_response(
            url=f"{instance_url}/tickets",
            json=[1, 2],
            headers=paging_headers(token=token),
        )

        result = service.execute_activity(CONNECTION_ID, "tickets")

        assert result.body == [1, 2]
        assert result.page is not None
        assert result.page.has_more and result.page.next_page_token == token

    def test_max_records_follows_pages(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        first, second = page_token("2"), page_token("3")
        httpx_mock.add_response(
            url=f"{instance_url}/tickets?pageSize=2",
            json=[1, 2],
            headers=paging_headers(token=first),
        )
        httpx_mock.add_response(
            url=f"{instance_url}/tickets?pageSize=2&nextPage={first}",
            json=[3, 4],
            headers=paging_headers(token=second),
        )
        httpx_mock.add_response(
            url=f"{instance_url}/tickets?pageSize=2&nextPage={second}",
            json=[5, 6],
            headers=paging_headers(token=page_token("4")),
        )

        result = service.execute_activity(
            CONNECTION_ID, "tickets", query_params={"pageSize": "2"}, max_records=5
        )

        assert result.body == [1, 2, 3, 4, 5]
        assert result.page is None
        assert "elements-has-more" not in result.headers
        assert "elements-next-page-token" not in result.headers
        assert len(httpx_mock.get_requests()) == 3

    def test_max_records_all_stops_at_done_token(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        first = page_token("2")
        httpx_mock.add_response(
            url=f"{instance_url}/tickets",
            json=[1],
            headers=paging_headers(token=first),
        )
        httpx_mock.add_response(
            url=f"{instance_url}/tickets?nextPage={first}",
            json=[2],
            headers=paging_headers(token=page_token("DONE")),
        )

        result = service.execute_activity(CONNECTION_ID, "tickets", max_records=-1)

        assert result.body == [1, 2]

    def test_max_records_within_first_page_keeps_page(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{instance_url}/tickets", json=[1, 2], headers=paging_headers()
        )

        result = service.execute_activity(CONNECTION_ID, "tickets", max_records=2)

        assert result.body == [1, 2]
        assert result.page is not None
        assert len(httpx_mock.get_requests()) == 1

    def test_failed_page_is_the_result(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        first = page_token("2")
        httpx_mock.add_response(
            url=f"{instance_url}/tickets",
            json=[1],
            headers=paging_headers(token=first),
        )
        httpx_mock.add_response(
            url=f"{instance_url}/tickets?nextPage={first}",
            status_code=500,
            json={"message": "boom"},
        )

        result = service.execute_activity(CONNECTION_ID, "tickets", max_records=10)

        assert result.status == 500 and result.body == {"message": "boom"}

    def test_opt_in_retry(
        self,
        httpx_mock: HTTPXMock,
        service: IntegrationService,
        instance_url: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("time.sleep", lambda _: None)
        httpx_mock.add_response(url=f"{instance_url}/tickets", status_code=503)
        httpx_mock.add_exception(httpx.ConnectError("down"))
        httpx_mock.add_response(url=f"{instance_url}/tickets", json=[1])

        result = service.execute_activity(CONNECTION_ID, "tickets", max_retries=2)

        assert result.ok and result.body == [1]
        assert len(httpx_mock.get_requests()) == 3

    def test_retry_gives_up_with_last_response(
        self,
        httpx_mock: HTTPXMock,
        service: IntegrationService,
        instance_url: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("time.sleep", lambda _: None)
        httpx_mock.add_response(
            url=f"{instance_url}/tickets", status_code=503, is_reusable=True
        )

        result = service.execute_activity(CONNECTION_ID, "tickets", max_retries=1)

        assert result.status == 503
        assert len(httpx_mock.get_requests()) == 2

    def test_post_is_not_retried_unless_listed(
        self,
        httpx_mock: HTTPXMock,
        service: IntegrationService,
        instance_url: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("time.sleep", lambda _: None)
        httpx_mock.add_response(
            url=f"{instance_url}/tickets", status_code=503, is_reusable=True
        )

        service.execute_activity(CONNECTION_ID, "tickets", "POST", max_retries=2)
        assert len(httpx_mock.get_requests()) == 1

        service.execute_activity(
            CONNECTION_ID, "tickets", "POST", max_retries=2, retry_methods=["post"]
        )
        assert len(httpx_mock.get_requests()) == 4

    def test_client_error_is_not_retried(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(url=f"{instance_url}/tickets", status_code=400)

        service.execute_activity(CONNECTION_ID, "tickets", max_retries=3)

        assert len(httpx_mock.get_requests()) == 1

    @pytest.mark.parametrize(
        "kwargs,message",
        [
            ({"connection_id": "", "object_name": "t"}, "connection_id is required"),
            ({"connection_id": "c", "object_name": ""}, "object_name is required"),
            ({"connection_id": "c", "object_name": "t", "method": "HEAD"}, "method"),
            (
                {"connection_id": "c", "object_name": "t", "max_records": 0},
                "max_records",
            ),
            (
                {
                    "connection_id": "c",
                    "object_name": "t",
                    "files": [ExecuteFile(name="", content=b"x")],
                },
                "needs a name",
            ),
            (
                {
                    "connection_id": "c",
                    "object_name": "t",
                    "folder_key": "k",
                    "folder_path": "p",
                },
                "Only one of folder_key or folder_path",
            ),
        ],
    )
    def test_validation(
        self,
        httpx_mock: HTTPXMock,
        service: IntegrationService,
        kwargs: Dict[str, Any],
        message: str,
    ) -> None:
        with pytest.raises(ValueError, match=message):
            service.execute_activity(**kwargs)
        assert httpx_mock.get_requests() == []

    def test_connection_overwrite_is_applied(
        self,
        httpx_mock: HTTPXMock,
        service: IntegrationService,
        base_url: str,
        org: str,
        tenant: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{base_url}{org}{tenant}/elements_/v3/element/instances/mapped/tickets",
            json=[],
        )
        token = _resource_overwrites.set(
            {
                f"connection.{CONNECTION_ID}": ConnectionResourceOverwrite(
                    resource_type="connection",
                    connection_id="mapped",
                    folder_key="mapped-folder",
                )
            }
        )
        try:
            service.execute_activity(CONNECTION_ID, "tickets", folder_path="Shared")
        finally:
            _resource_overwrites.reset(token)

        assert sent(httpx_mock).headers[HEADER_FOLDER_KEY] == "mapped-folder"

    async def test_async_get_and_paging(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        first = page_token("2")
        httpx_mock.add_response(
            url=f"{instance_url}/tickets",
            json=[1],
            headers=paging_headers(token=first),
        )
        httpx_mock.add_response(
            url=f"{instance_url}/tickets?nextPage={first}",
            json=[2],
            headers=paging_headers(has_more=False),
        )

        result = await service.execute_activity_async(
            CONNECTION_ID, "tickets", max_records=-1
        )

        assert result.body == [1, 2]

    async def test_async_non_2xx_is_returned(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{instance_url}/tickets", status_code=401, text="denied"
        )

        result = await service.execute_activity_async(
            CONNECTION_ID, "tickets", "POST", body={"a.b": 1}
        )

        assert result.status == 401 and result.body == "denied"
        assert json.loads(sent(httpx_mock).content) == {"a": {"b": 1}}


class TestExecuteActivityV4:
    def test_runs_on_the_v4_engine(
        self, httpx_mock: HTTPXMock, service: IntegrationService, v4_url: str
    ) -> None:
        httpx_mock.add_response(
            url=v4_url,
            json={"status": 200, "headers": {"x-v": ["a", "b"]}, "body": {"ts": "1"}},
            headers=paging_headers(),
        )

        result = service.execute_activity(
            CONNECTION_ID,
            "SendMessageToChannel",
            "POST",
            connector_version="4.0.0",
            connector_key="uipath-salesforce-slack",
            query_params={"send_as": "bot"},
            headers={"X-Trace": "t"},
            body={"channel": "C1", "blocks[0].type": "section"},
            folder_key="f1",
            # None of these apply on the version 4 engine
            url_input_fields=["send_as"],
            file_response=True,
            max_records=5,
        )

        assert isinstance(result, ExecuteActivityResult)
        assert result.model_dump() == {
            "ok": True,
            "status": 200,
            "status_text": "",
            "body": {"ts": "1"},
            "headers": {"x-v": "a, b"},
            "page": None,
        }
        request = sent(httpx_mock)
        assert request.method == "POST"
        assert request.url.query == b""
        assert request.headers[HEADER_FOLDER_KEY] == "f1"
        assert "x-trace" not in request.headers
        assert json.loads(request.content) == {
            "context": {
                "connectionId": CONNECTION_ID,
                "connectorKey": "uipath-salesforce-slack",
                "script": {"reference": "SendMessageToChannel"},
            },
            "request": {
                "body": {"channel": "C1", "blocks": [{"type": "section"}]},
                "query": {"send_as": "bot"},
                "headers": {"X-Trace": "t"},
            },
        }
        assert len(httpx_mock.get_requests()) == 1

    def test_script_ref_overrides_object_name_and_empty_request(
        self, httpx_mock: HTTPXMock, service: IntegrationService, v4_url: str
    ) -> None:
        httpx_mock.add_response(url=v4_url, json={"status": 200, "body": []})

        service.execute_activity(
            CONNECTION_ID,
            "ListChannels",
            "POST",
            connector_version="v5",
            connector_key="uipath-x",
            script_ref="scripts/list-channels",
        )

        assert json.loads(sent(httpx_mock).content) == {
            "context": {
                "connectionId": CONNECTION_ID,
                "connectorKey": "uipath-x",
                "script": {"reference": "scripts/list-channels"},
            },
            # A write without a body is not given `{}` on the version 4 engine
            "request": {},
        }

    def test_vendor_error_is_returned(
        self, httpx_mock: HTTPXMock, service: IntegrationService, v4_url: str
    ) -> None:
        httpx_mock.add_response(
            url=v4_url, json={"status": 404, "body": {"error": "channel_not_found"}}
        )

        result = service.execute_activity(
            CONNECTION_ID, "GetChannel", connector_version="4.0.0", connector_key="k"
        )

        assert not result.ok and result.status == 404
        assert result.body == {"error": "channel_not_found"}
        assert not hasattr(result, "is_vendor_error")

    def test_engine_failure_is_returned_as_is(
        self, httpx_mock: HTTPXMock, service: IntegrationService, v4_url: str
    ) -> None:
        httpx_mock.add_response(
            url=v4_url, status_code=400, json={"error": "unknown script"}
        )

        result = service.execute_activity(
            CONNECTION_ID, "Nope", connector_version="4.0.0", connector_key="k"
        )

        assert result.status == 400 and result.body == {"error": "unknown script"}

    def test_older_version_stays_on_v3(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(url=f"{instance_url}/tickets", json=[])

        assert service.execute_activity(
            CONNECTION_ID, "tickets", connector_version="3.9.0", headers={"X": "1"}
        ).ok
        assert "x" not in sent(httpx_mock).headers

    def test_retry_follows_the_activity_method(
        self,
        httpx_mock: HTTPXMock,
        service: IntegrationService,
        v4_url: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("time.sleep", lambda _: None)
        httpx_mock.add_response(url=v4_url, status_code=503, is_reusable=True)
        v4 = {"connector_version": "4.0.0", "connector_key": "k"}

        service.execute_activity(CONNECTION_ID, "Send", "POST", max_retries=2, **v4)
        assert len(httpx_mock.get_requests()) == 1

        service.execute_activity(CONNECTION_ID, "List", "GET", max_retries=2, **v4)
        assert len(httpx_mock.get_requests()) == 4

    @pytest.mark.parametrize(
        "kwargs,message",
        [
            ({}, "connector_key is required"),
            (
                {
                    "connector_key": "k",
                    "files": [ExecuteFile(name="file", content=b"x")],
                },
                "files are not supported",
            ),
            ({"connector_key": "k", "max_records": 0}, "max_records"),
        ],
    )
    def test_validation(
        self,
        httpx_mock: HTTPXMock,
        service: IntegrationService,
        kwargs: Dict[str, Any],
        message: str,
    ) -> None:
        with pytest.raises(ValueError, match=message):
            service.execute_activity(
                CONNECTION_ID, "Send", "POST", connector_version="4.0.0", **kwargs
            )
        assert httpx_mock.get_requests() == []

    async def test_async(
        self, httpx_mock: HTTPXMock, service: IntegrationService, v4_url: str
    ) -> None:
        httpx_mock.add_response(url=v4_url, json={"status": 201, "body": {"id": 1}})

        result = await service.execute_activity_async(
            CONNECTION_ID,
            "Create",
            "POST",
            connector_version="4.0.0",
            connector_key="k",
            body={"a.b": 1},
        )

        assert result.ok and result.status == 201 and result.body == {"id": 1}
        assert json.loads(sent(httpx_mock).content)["request"] == {
            "body": {"a": {"b": 1}}
        }


class TestExecuteHttp:
    def test_v3_passthrough(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{instance_url}/http-request",
            json={
                "code": 201,
                "statusText": "Created",
                "headers": {"x-v": "1"},
                "body": {"id": 7},
            },
        )

        result = service.execute_http(
            CONNECTION_ID,
            "/v2/tickets",
            "POST",
            headers={"X-Src": "app"},
            query_params={"notify": "true"},
            body={"subject": "s"},
            folder_key="f1",
        )

        assert isinstance(result, ExecuteHttpResult)
        assert result.model_dump() == {
            "ok": True,
            "status": 201,
            "status_text": "Created",
            "body": {"id": 7},
            "headers": {"x-v": "1"},
            "is_vendor_error": False,
        }
        request = sent(httpx_mock)
        assert request.method == "POST"
        assert request.headers[HEADER_FOLDER_KEY] == "f1"
        assert json.loads(request.content) == {
            "method": "POST",
            "url": "/v2/tickets",
            "headers": {"X-Src": "app"},
            "query": {"notify": "true"},
            "body": '{"subject": "s"}',
        }

    def test_v3_minimal_request_and_string_body(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{instance_url}/http-request", json={"code": 200}, is_reusable=True
        )

        service.execute_http(CONNECTION_ID, "/v2/tickets")
        assert json.loads(sent(httpx_mock).content) == {
            "method": "GET",
            "url": "/v2/tickets",
        }

        service.execute_http(CONNECTION_ID, "/v2/tickets", "PUT", body="raw")
        assert json.loads(sent(httpx_mock).content)["body"] == "raw"

    def test_v3_vendor_error(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{instance_url}/http-request",
            json={"code": 404, "rawStringBody": "missing"},
        )

        result = service.execute_http(CONNECTION_ID, "/v2/none")

        assert not result.ok and result.status == 404
        assert result.is_vendor_error and result.body == "missing"

    def test_integration_service_failure_is_not_a_vendor_error(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(
            url=f"{instance_url}/http-request",
            status_code=403,
            json={"message": "forbidden"},
        )

        result = service.execute_http(CONNECTION_ID, "/v2/tickets")

        assert result.status == 403 and not result.is_vendor_error
        assert result.body == {"message": "forbidden"}

    def test_older_connector_version_uses_v3(
        self, httpx_mock: HTTPXMock, service: IntegrationService, instance_url: str
    ) -> None:
        httpx_mock.add_response(url=f"{instance_url}/http-request", json={"code": 200})

        assert service.execute_http(CONNECTION_ID, "/x", connector_version="3.2.1").ok

    def test_v4_engine(
        self, httpx_mock: HTTPXMock, service: IntegrationService, v4_url: str
    ) -> None:
        httpx_mock.add_response(
            url=v4_url,
            json={"status": 200, "headers": {"h": ["a", "b"]}, "body": {"ok": 1}},
        )

        result = service.execute_http(
            CONNECTION_ID,
            "https://api.example.com/v2/tickets",
            query_params={"a": "1"},
            connector_version="4.0.0",
            connector_key="uipath-x",
        )

        assert result.ok and result.body == {"ok": 1}
        assert result.headers == {"h": "a, b"}
        assert json.loads(sent(httpx_mock).content) == {
            "outboundRequestConfig": {
                "method": "GET",
                "url": "https://api.example.com/v2/tickets?a=1",
            },
            "context": {"connectionId": CONNECTION_ID, "connectorKey": "uipath-x"},
        }

    def test_v4_vendor_error(
        self, httpx_mock: HTTPXMock, service: IntegrationService, v4_url: str
    ) -> None:
        httpx_mock.add_response(url=v4_url, json={"status": 404, "body": "nope"})

        result = service.execute_http(
            CONNECTION_ID, "https://api.example.com/x", connector_version="4.1"
        )

        assert result.status == 404 and result.is_vendor_error

    def test_v4_file_upload(
        self, httpx_mock: HTTPXMock, service: IntegrationService, v4_url: str
    ) -> None:
        httpx_mock.add_response(url=v4_url, json={"status": 200})

        service.execute_http(
            CONNECTION_ID,
            "https://api.example.com/files",
            "PUT",
            connector_version="4.0.0",
            file=ExecuteFile(
                name="file", content=b"%PDF-1", content_type="application/pdf"
            ),
        )

        request = sent(httpx_mock)
        assert request.headers["content-type"].startswith("multipart/form-data")
        content = request.content
        assert content.index(b'name="manifest"') < content.index(b'name="file"')
        assert b'"bodyRef": "file"' in content
        assert (
            b'"attachments": [{"name": "file", "size": 6, "contentType": "application/pdf"}]'
            in content
        )
        assert b"Content-Type: application/pdf\r\n\r\n%PDF-1" in content

    def test_v4_binary_download(
        self, httpx_mock: HTTPXMock, service: IntegrationService, v4_url: str
    ) -> None:
        document = (
            b'--xyz\r\nContent-Type: application/json\r\n\r\n{"status": 200, "headers": {"content-type": "image/png"}}'
            b"\r\n--xyz\r\nContent-Type: application/octet-stream\r\n\r\n\x89PNG\r\n\x00"
            b"\r\n--xyz--\r\n"
        )
        httpx_mock.add_response(
            url=v4_url,
            content=document,
            headers={"content-type": "multipart/mixed; boundary=xyz"},
        )

        result = service.execute_http(
            CONNECTION_ID, "https://api.example.com/img", connector_version="4.0.0"
        )

        assert result.ok and result.body == b"\x89PNG\r\n\x00"
        assert result.headers == {"content-type": "image/png"}

    def test_retry_follows_vendor_method(
        self,
        httpx_mock: HTTPXMock,
        service: IntegrationService,
        instance_url: str,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr("time.sleep", lambda _: None)
        httpx_mock.add_response(
            url=f"{instance_url}/http-request", status_code=502, is_reusable=True
        )

        service.execute_http(CONNECTION_ID, "/x", "POST", max_retries=2)
        assert len(httpx_mock.get_requests()) == 1

        service.execute_http(CONNECTION_ID, "/x", "GET", max_retries=2)
        assert len(httpx_mock.get_requests()) == 4

    @pytest.mark.parametrize(
        "kwargs,message",
        [
            ({"connection_id": "c", "url": ""}, "url is required"),
            ({"connection_id": "", "url": "/x"}, "connection_id is required"),
            (
                {
                    "connection_id": "c",
                    "url": "/x",
                    "file": ExecuteFile(name="f", content=b"x"),
                },
                "version 4 connector",
            ),
            (
                {
                    "connection_id": "c",
                    "url": "https://x",
                    "connector_version": "4.0.0",
                    "body": {"a": 1},
                    "file": ExecuteFile(name="f", content=b"x"),
                },
                "file and body cannot both",
            ),
        ],
    )
    def test_validation(
        self,
        httpx_mock: HTTPXMock,
        service: IntegrationService,
        kwargs: Dict[str, Any],
        message: str,
    ) -> None:
        with pytest.raises(ValueError, match=message):
            service.execute_http(**kwargs)
        assert httpx_mock.get_requests() == []

    async def test_async_v3_and_v4(
        self,
        httpx_mock: HTTPXMock,
        service: IntegrationService,
        instance_url: str,
        v4_url: str,
    ) -> None:
        httpx_mock.add_response(
            url=f"{instance_url}/http-request", json={"code": 500, "body": {"e": 1}}
        )
        httpx_mock.add_response(url=v4_url, json={"status": 200, "body": "ok"})

        v3 = await service.execute_http_async(CONNECTION_ID, "/x")
        v4 = await service.execute_http_async(
            CONNECTION_ID, "https://api.example.com/x", connector_version="4.0.0"
        )

        assert v3.status == 500 and v3.is_vendor_error and v3.body == {"e": 1}
        assert v4.ok and v4.body == "ok"


def test_sdk_exposes_integration_service_and_leaves_connections_alone() -> None:
    from uipath.platform import UiPath
    from uipath.platform.connections import ConnectionsService

    sdk = UiPath(base_url="https://test.uipath.com/org/tenant", secret="secret")

    assert isinstance(sdk.integration_service, IntegrationService)
    assert isinstance(sdk.connections, ConnectionsService)
    assert not hasattr(sdk.connections, "execute_activity")
