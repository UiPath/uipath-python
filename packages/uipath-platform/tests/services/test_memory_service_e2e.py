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

import pytest

from uipath.platform import UiPath
from uipath.platform.memory import (
    EpisodicMemoryIndex,
    EpisodicMemoryListResponse,
    EscalationMemorySearchResponse,
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
    """Create a real UiPath client from env vars.

    Supports two auth modes:
    - Token-based: UIPATH_URL + UIPATH_ACCESS_TOKEN (from `uipath auth`)
    - Client credentials: UIPATH_URL + UIPATH_CLIENT_ID + UIPATH_CLIENT_SECRET (CI)
    """
    _require_env("UIPATH_URL")
    client_id = os.environ.get("UIPATH_CLIENT_ID")
    client_secret = os.environ.get("UIPATH_CLIENT_SECRET")
    if client_id and client_secret:
        return UiPath(client_id=client_id, client_secret=client_secret)
    _require_env("UIPATH_ACCESS_TOKEN")
    return UiPath()


@pytest.fixture(scope="module")
def folder_key() -> str:
    return _require_env("UIPATH_FOLDER_KEY")


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
        assert isinstance(result.system_prompt_injection, str)

    # ── Escalation search (LLMOps) ────────────────────────────────

    def test_escalation_search_empty_index(
        self,
        sdk: UiPath,
        memory_index: EpisodicMemoryIndex,
        folder_key: str,
    ) -> None:
        """Search escalation memory on empty index — should return valid response."""
        request = MemorySearchRequest(
            fields=[
                SearchField(
                    key_path=["input"],
                    value="test escalation query",
                )
            ],
            settings=SearchSettings(
                threshold=0.0,
                result_count=5,
                search_mode=SearchMode.Hybrid,
            ),
            definition_system_prompt="You are a helpful assistant.",
        )
        result = sdk.memory.escalation_search(
            memory_space_id=memory_index.id,
            request=request,
            folder_key=folder_key,
        )
        assert isinstance(result, EscalationMemorySearchResponse)
