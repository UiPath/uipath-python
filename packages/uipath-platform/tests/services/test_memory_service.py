"""Unit tests for MemoryService with HTTP mocking."""

import json

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.memory import (
    EpisodicMemoryIndex,
    EpisodicMemoryListResponse,
    EscalationMemoryIngestRequest,
    EscalationMemorySearchResponse,
    MemoryMatch,
    MemoryMatchField,
    MemorySearchRequest,
    MemorySearchResponse,
    SearchField,
    SearchMode,
    SearchSettings,
)
from uipath.platform.memory._memory_service import MemoryService
from uipath.platform.orchestrator._folder_service import FolderService


@pytest.fixture
def folder_service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
) -> FolderService:
    return FolderService(config=config, execution_context=execution_context)


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    folder_service: FolderService,
    monkeypatch: pytest.MonkeyPatch,
) -> MemoryService:
    monkeypatch.setenv("UIPATH_FOLDER_KEY", "test-folder-key")
    return MemoryService(
        config=config,
        execution_context=execution_context,
        folders_service=folder_service,
    )


# ── Sample response payloads ──────────────────────────────────────────

SAMPLE_INDEX = {
    "id": "aaaa-bbbb-cccc-dddd",
    "name": "test-memory-space",
    "description": "A test memory space",
    "lastQueried": "2026-03-30T00:00:00Z",
    "memoriesCount": 5,
    "folderKey": "test-folder-key",
    "createdByUserId": "user-123",
    "isEncrypted": False,
}

SAMPLE_LIST_RESPONSE = {"value": [SAMPLE_INDEX]}

SAMPLE_SEARCH_RESPONSE = {
    "results": [
        {
            "memoryItemId": "item-001",
            "score": 0.95,
            "semanticScore": 0.92,
            "weightedScore": 0.93,
            "fields": [
                {
                    "keyPath": ["input"],
                    "value": "What is the capital of France?",
                    "weight": 1.0,
                    "score": 0.95,
                    "weightedScore": 0.95,
                }
            ],
            "span": None,
            "feedback": None,
        }
    ],
    "metadata": {"queryTime": "12ms"},
    "systemPromptInjection": "Based on past interactions: Paris is the capital.",
}

SAMPLE_ESCALATION_SEARCH_RESPONSE = {
    "results": [
        {
            "answer": {
                "output": {"action": "approve", "reason": "meets criteria"},
                "outcome": "approved",
            }
        }
    ],
}


class TestMemoryService:
    """Unit tests for MemoryService."""

    class TestCreate:
        def test_create_memory_space(
            self,
            httpx_mock: HTTPXMock,
            service: MemoryService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/episodicmemories/create",
                status_code=200,
                json=SAMPLE_INDEX,
            )

            result = service.create(
                name="test-memory-space",
                description="A test memory space",
            )

            assert isinstance(result, EpisodicMemoryIndex)
            assert result.id == "aaaa-bbbb-cccc-dddd"
            assert result.name == "test-memory-space"
            assert result.memories_count == 5

            sent = httpx_mock.get_request()
            assert sent is not None
            assert sent.method == "POST"
            body = json.loads(sent.content)
            assert body["name"] == "test-memory-space"
            assert body["description"] == "A test memory space"

        def test_create_sends_folder_header(
            self,
            httpx_mock: HTTPXMock,
            service: MemoryService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/episodicmemories/create",
                status_code=200,
                json=SAMPLE_INDEX,
            )

            service.create(name="test", folder_key="custom-folder-key")

            sent = httpx_mock.get_request()
            assert sent is not None
            assert sent.headers.get("x-uipath-folderkey") == "custom-folder-key"

        def test_create_with_encryption(
            self,
            httpx_mock: HTTPXMock,
            service: MemoryService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/episodicmemories/create",
                status_code=200,
                json={**SAMPLE_INDEX, "isEncrypted": True},
            )

            result = service.create(
                name="encrypted-space",
                is_encrypted=True,
            )

            assert result.is_encrypted is True
            sent = httpx_mock.get_request()
            assert sent is not None
            body = json.loads(sent.content)
            assert body["isEncrypted"] is True

    class TestList:
        def test_list_memory_spaces(
            self,
            httpx_mock: HTTPXMock,
            service: MemoryService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/episodicmemories",
                status_code=200,
                json=SAMPLE_LIST_RESPONSE,
            )

            result = service.list()

            assert isinstance(result, EpisodicMemoryListResponse)
            assert len(result.value) == 1
            assert result.value[0].name == "test-memory-space"

        def test_list_with_odata_params(
            self,
            httpx_mock: HTTPXMock,
            service: MemoryService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/episodicmemories?%24filter=Name+eq+%27test%27&%24orderby=Name+asc&%24top=10&%24skip=5",
                status_code=200,
                json=SAMPLE_LIST_RESPONSE,
            )

            result = service.list(
                filter="Name eq 'test'",
                orderby="Name asc",
                top=10,
                skip=5,
            )

            assert isinstance(result, EpisodicMemoryListResponse)

        def test_list_empty(
            self,
            httpx_mock: HTTPXMock,
            service: MemoryService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/episodicmemories",
                status_code=200,
                json={"value": []},
            )

            result = service.list()

            assert isinstance(result, EpisodicMemoryListResponse)
            assert len(result.value) == 0

    class TestSearch:
        def test_search_memory(
            self,
            httpx_mock: HTTPXMock,
            service: MemoryService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            memory_space_id = "aaaa-bbbb-cccc-dddd"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/llmopstenant_/api/Agent/memory/{memory_space_id}/search",
                status_code=200,
                json=SAMPLE_SEARCH_RESPONSE,
            )

            request = MemorySearchRequest(
                fields=[
                    SearchField(
                        key_path=["input"],
                        value="What is the capital of France?",
                    )
                ],
                settings=SearchSettings(
                    threshold=0.0,
                    result_count=5,
                    search_mode=SearchMode.Hybrid,
                ),
                definition_system_prompt="You are a helpful assistant.",
            )

            result = service.search(
                memory_space_id=memory_space_id,
                request=request,
            )

            assert isinstance(result, MemorySearchResponse)
            assert len(result.results) == 1
            assert isinstance(result.results[0], MemoryMatch)
            assert result.results[0].memory_item_id == "item-001"
            assert result.results[0].score == 0.95
            assert isinstance(result.results[0].fields[0], MemoryMatchField)
            assert (
                result.system_prompt_injection
                == "Based on past interactions: Paris is the capital."
            )

            sent = httpx_mock.get_request()
            assert sent is not None
            assert sent.method == "POST"
            body = json.loads(sent.content)
            assert body["fields"][0]["keyPath"] == ["input"]
            assert body["settings"]["searchMode"] == "Hybrid"
            assert body["definitionSystemPrompt"] == "You are a helpful assistant."

        def test_search_sends_folder_header(
            self,
            httpx_mock: HTTPXMock,
            service: MemoryService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            memory_space_id = "aaaa-bbbb-cccc-dddd"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/llmopstenant_/api/Agent/memory/{memory_space_id}/search",
                status_code=200,
                json=SAMPLE_SEARCH_RESPONSE,
            )

            request = MemorySearchRequest(
                fields=[SearchField(key_path=["input"], value="test")],
                settings=SearchSettings(
                    threshold=0.0,
                    result_count=1,
                    search_mode=SearchMode.Semantic,
                ),
            )

            service.search(
                memory_space_id=memory_space_id,
                request=request,
                folder_key="custom-folder",
            )

            sent = httpx_mock.get_request()
            assert sent is not None
            assert sent.headers.get("x-uipath-folderkey") == "custom-folder"

    class TestEscalationSearch:
        def test_escalation_search(
            self,
            httpx_mock: HTTPXMock,
            service: MemoryService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            memory_space_id = "aaaa-bbbb-cccc-dddd"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/llmopstenant_/api/Agent/memory/{memory_space_id}/escalation/search",
                status_code=200,
                json=SAMPLE_ESCALATION_SEARCH_RESPONSE,
            )

            request = MemorySearchRequest(
                fields=[SearchField(key_path=["input"], value="approval request")],
                settings=SearchSettings(
                    threshold=0.0,
                    result_count=5,
                    search_mode=SearchMode.Hybrid,
                ),
            )

            result = service.escalation_search(
                memory_space_id=memory_space_id,
                request=request,
            )

            assert isinstance(result, EscalationMemorySearchResponse)
            assert result.results is not None
            assert len(result.results) == 1
            assert result.results[0].answer is not None
            assert result.results[0].answer.outcome == "approved"

            sent = httpx_mock.get_request()
            assert sent is not None
            assert sent.method == "POST"
            assert "/escalation/search" in str(sent.url)

        def test_escalation_search_empty_results(
            self,
            httpx_mock: HTTPXMock,
            service: MemoryService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            memory_space_id = "aaaa-bbbb-cccc-dddd"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/llmopstenant_/api/Agent/memory/{memory_space_id}/escalation/search",
                status_code=200,
                json={"results": None},
            )

            request = MemorySearchRequest(
                fields=[SearchField(key_path=["input"], value="no match")],
                settings=SearchSettings(
                    threshold=0.0,
                    result_count=1,
                    search_mode=SearchMode.Hybrid,
                ),
            )

            result = service.escalation_search(
                memory_space_id=memory_space_id,
                request=request,
            )

            assert isinstance(result, EscalationMemorySearchResponse)
            assert result.results is None

    class TestEscalationIngest:
        def test_escalation_ingest(
            self,
            httpx_mock: HTTPXMock,
            service: MemoryService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            memory_space_id = "aaaa-bbbb-cccc-dddd"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/llmopstenant_/api/Agent/memory/{memory_space_id}/escalation/ingest",
                status_code=200,
            )

            request = EscalationMemoryIngestRequest(
                span_id="span-123",
                trace_id="trace-456",
                answer='{"action": "approve"}',
                attributes='{"input": "approve this?"}',
                user_id="user-789",
            )

            service.escalation_ingest(
                memory_space_id=memory_space_id,
                request=request,
            )

            sent = httpx_mock.get_request()
            assert sent is not None
            assert sent.method == "POST"
            assert "/escalation/ingest" in str(sent.url)
            body = json.loads(sent.content)
            assert body["spanId"] == "span-123"
            assert body["traceId"] == "trace-456"
            assert body["answer"] == '{"action": "approve"}'
            assert body["attributes"] == '{"input": "approve this?"}'
            assert body["userId"] == "user-789"

        def test_escalation_ingest_sends_folder_header(
            self,
            httpx_mock: HTTPXMock,
            service: MemoryService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            memory_space_id = "aaaa-bbbb-cccc-dddd"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/llmopstenant_/api/Agent/memory/{memory_space_id}/escalation/ingest",
                status_code=200,
            )

            request = EscalationMemoryIngestRequest(
                span_id="s1",
                trace_id="t1",
                answer="yes",
                attributes="{}",
            )

            service.escalation_ingest(
                memory_space_id=memory_space_id,
                request=request,
                folder_key="my-folder",
            )

            sent = httpx_mock.get_request()
            assert sent is not None
            assert sent.headers.get("x-uipath-folderkey") == "my-folder"

        def test_escalation_ingest_excludes_none_user_id(
            self,
            httpx_mock: HTTPXMock,
            service: MemoryService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            memory_space_id = "aaaa-bbbb-cccc-dddd"
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/llmopstenant_/api/Agent/memory/{memory_space_id}/escalation/ingest",
                status_code=200,
            )

            request = EscalationMemoryIngestRequest(
                span_id="s1",
                trace_id="t1",
                answer="yes",
                attributes="{}",
            )

            service.escalation_ingest(
                memory_space_id=memory_space_id,
                request=request,
            )

            sent = httpx_mock.get_request()
            assert sent is not None
            body = json.loads(sent.content)
            assert "userId" not in body
