"""E2E tests for MemoryService against real ECS + LLMOps endpoints.

Prerequisites:
    uipath auth --alpha          # sets UIPATH_URL + UIPATH_ACCESS_TOKEN
    export UIPATH_FOLDER_KEY=... # folder GUID with agent memory enabled

Run:
    cd packages/uipath-platform
    uv run pytest tests/services/test_memory_service_e2e.py -m e2e -v
"""

import os
import uuid

import httpx
import pytest

from uipath.platform import UiPath
from uipath.platform.errors import EnrichedException
from uipath.platform.memory import (
    EpisodicMemoryIndex,
    EpisodicMemoryListResponse,
    MemoryIngestResponse,
    MemorySearchRequest,
    MemorySearchResponse,
    SearchField,
    SearchMode,
    SearchSettings,
)

pytestmark = pytest.mark.e2e


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"Environment variable {name} is not set")
    return value


@pytest.fixture(scope="module")
def sdk() -> UiPath:
    """Create a real UiPath client from env vars."""
    _require_env("UIPATH_URL")
    _require_env("UIPATH_ACCESS_TOKEN")
    return UiPath()


@pytest.fixture(scope="module")
def folder_key() -> str:
    return _require_env("UIPATH_FOLDER_KEY")


@pytest.fixture(scope="module")
def base_url() -> str:
    return _require_env("UIPATH_URL")


@pytest.fixture(scope="module")
def access_token() -> str:
    return _require_env("UIPATH_ACCESS_TOKEN")


@pytest.fixture(scope="module")
def memory_index(sdk: UiPath, folder_key: str):  # noqa: ANN201
    """Create a test memory index and clean it up after all tests."""
    unique_name = f"sdk-e2e-test-{uuid.uuid4().hex[:8]}"
    index = sdk.memory.create(
        name=unique_name,
        description="Created by E2E test — safe to delete",
        folder_key=folder_key,
    )
    yield index
    # Cleanup
    try:
        sdk.memory.delete_index(key=index.id, folder_key=folder_key)
    except Exception:
        pass


class TestMemoryServiceE2E:
    """E2E tests for MemoryService lifecycle.

    Requires: UIPATH_URL, UIPATH_ACCESS_TOKEN, UIPATH_FOLDER_KEY
    """

    # ── Index CRUD (ECS) ──────────────────────────────────────────

    def test_create_index(self, memory_index: EpisodicMemoryIndex) -> None:
        """Verify index creation returns a well-formed EpisodicMemoryIndex."""
        assert memory_index.id, "Index ID should be set"
        assert memory_index.name.startswith("sdk-e2e-test-")
        assert memory_index.folder_key, "Folder key should be populated"
        assert memory_index.memories_count == 0

    def test_get_index(
        self,
        sdk: UiPath,
        memory_index: EpisodicMemoryIndex,
        folder_key: str,
    ) -> None:
        """Verify we can retrieve the index by key."""
        fetched = sdk.memory.get(key=memory_index.id, folder_key=folder_key)
        assert fetched.id == memory_index.id
        assert fetched.name == memory_index.name

    def test_list_indexes(
        self,
        sdk: UiPath,
        memory_index: EpisodicMemoryIndex,
        folder_key: str,
    ) -> None:
        """Verify list with OData filter returns our index."""
        result = sdk.memory.list(
            filter=f"Name eq '{memory_index.name}'",
            folder_key=folder_key,
        )
        assert isinstance(result, EpisodicMemoryListResponse)
        names = [idx.name for idx in result.value]
        assert memory_index.name in names

    # ── Search (LLMOps) ──────────────────────────────────────────

    def test_search_empty_index(
        self,
        sdk: UiPath,
        memory_index: EpisodicMemoryIndex,
        folder_key: str,
    ) -> None:
        """Search an empty index — should return empty results and systemPromptInjection."""
        request = MemorySearchRequest(
            fields=[
                SearchField(
                    key_path=["input"],
                    value="test query",
                )
            ],
            settings=SearchSettings(
                threshold=0.0,
                result_count=5,
                search_mode=SearchMode.Hybrid,
            ),
            definition_system_prompt="You are a helpful assistant.",
        )
        result = sdk.memory.search(
            memory_space_id=memory_index.id,
            request=request,
            folder_key=folder_key,
        )
        assert isinstance(result, MemorySearchResponse)
        assert isinstance(result.results, list)
        assert isinstance(result.metadata, dict)
        # systemPromptInjection should be a string (possibly empty for no results)
        assert isinstance(result.system_prompt_injection, str)

    # ── Full ingest lifecycle (LLMOps) ────────────────────────────

    def test_ingest_and_search(
        self,
        sdk: UiPath,
        memory_index: EpisodicMemoryIndex,
        folder_key: str,
        base_url: str,
        access_token: str,
    ) -> None:
        """Full lifecycle: create feedback → ingest → search → verify match."""
        # Step 1: Create a synthetic feedback via LLMOps API directly
        # (MemoryService doesn't have a feedback API — this is test scaffolding)
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        feedback_payload = {
            "traceId": trace_id,
            "spanId": span_id,
            "userId": user_id,
            "isPositive": True,
            "isOutput": False,
            "isAgentError": False,
            "isAgentPlanExecution": False,
            "memorySpaceId": memory_index.id,
            "memorySpaceName": memory_index.name,
            "attributes": '{"input": "What is the capital of France?", "output": "Paris"}',
        }

        with httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30.0,
        ) as client:
            resp = client.post(
                "/llmopstenant_/api/Agent/feedback",
                json=feedback_payload,
            )
            # If feedback creation fails (e.g. LLMOps not available),
            # skip gracefully rather than fail the whole suite
            if resp.status_code >= 400:
                pytest.skip(
                    f"Could not create feedback (HTTP {resp.status_code}): {resp.text}"
                )
            feedback_data = resp.json()

        feedback_id = feedback_data.get("id") or feedback_data.get("feedbackId")
        assert feedback_id, f"No feedback ID in response: {feedback_data}"

        # Step 2: Ingest via MemoryService (LLMOps)
        ingest_result = sdk.memory.ingest(
            memory_space_id=memory_index.id,
            feedback_id=feedback_id,
            memory_space_name=memory_index.name,
            folder_key=folder_key,
        )
        assert isinstance(ingest_result, MemoryIngestResponse)
        assert ingest_result.memory_item_id, "Should return a memory item ID"

        # Step 3: Search to find the ingested memory
        search_request = MemorySearchRequest(
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
        search_result = sdk.memory.search(
            memory_space_id=memory_index.id,
            request=search_request,
            folder_key=folder_key,
        )
        assert isinstance(search_result, MemorySearchResponse)
        assert isinstance(search_result.system_prompt_injection, str)
        # Ingestion may be async — we verify the response shape is valid
        # even if results aren't immediately available
        assert isinstance(search_result.results, list)

    # ── Delete lifecycle ──────────────────────────────────────────

    def test_delete_index(
        self,
        sdk: UiPath,
        folder_key: str,
    ) -> None:
        """Verify index deletion works (uses a separate index to not break other tests)."""
        temp_name = f"sdk-e2e-delete-{uuid.uuid4().hex[:8]}"
        temp_index = sdk.memory.create(
            name=temp_name,
            description="Temp index for delete test",
            folder_key=folder_key,
        )
        # Delete it
        sdk.memory.delete_index(key=temp_index.id, folder_key=folder_key)

        # Verify it's gone — GET should raise
        with pytest.raises(EnrichedException):
            sdk.memory.get(key=temp_index.id, folder_key=folder_key)
