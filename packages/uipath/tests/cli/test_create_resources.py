"""Unit tests for cli_push.create_resources virtual-resource fallback."""

import json
import os
from types import SimpleNamespace
from typing import Any, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from uipath._cli._utils._studio_project import (
    Status,
    VirtualResourceResult,
)
from uipath.platform.errors import EnrichedException, FolderNotFoundException


def _enriched_exc(
    status_code: int = 404, body: bytes = b"not found"
) -> EnrichedException:
    """Build an EnrichedException backed by a real HTTPStatusError."""
    request = httpx.Request("GET", "https://example.test/x")
    response = httpx.Response(status_code, content=body, request=request)
    http_err = httpx.HTTPStatusError("x", request=request, response=response)
    return EnrichedException(http_err)


class _AsyncIterator:
    """Minimal async iterator with aclose() to mimic resource_catalog pagination."""

    def __init__(self, items: List[Any], raise_exc: Optional[Exception] = None):
        self._items = iter(items)
        self._raise_exc = raise_exc
        self.aclose = AsyncMock()

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._raise_exc is not None:
            raise self._raise_exc
        try:
            return next(self._items)
        except StopIteration:
            raise StopAsyncIteration from None


def _make_bindings(resources: List[dict[str, Any]]) -> str:
    return json.dumps({"version": "2.2", "resources": resources})


def _asset_binding(
    name: str = "my_asset",
    folder_path: str = "Shared",
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    return {
        "resource": "asset",
        "key": f"binding-{name}",
        "value": {
            "name": {
                "defaultValue": name,
                "isExpression": False,
                "displayName": "name",
            },
            "folderPath": {
                "defaultValue": folder_path,
                "isExpression": False,
                "displayName": "folderPath",
            },
        },
        "metadata": metadata,
    }


def _found_resource(
    key: str = "resource-key",
    resource_type: str = "asset",
    resource_sub_type: str = "stringAsset",
    folder_path: str = "Shared",
) -> SimpleNamespace:
    folder = SimpleNamespace(
        key="folder-key",
        fully_qualified_name=folder_path,
        path=folder_path,
    )
    return SimpleNamespace(
        resource_key=key,
        resource_type=resource_type,
        resource_sub_type=resource_sub_type,
        folders=[folder],
    )


@pytest.fixture
def bindings_file(tmp_path, monkeypatch):
    """Write a bindings file to a tmp path and patch UiPathConfig.bindings_file_path."""
    path = tmp_path / "bindings.json"

    def _writer(content: str) -> str:
        path.write_text(content, encoding="utf-8")
        return str(path)

    from uipath.platform.common._config import ConfigurationManager

    monkeypatch.setattr(
        ConfigurationManager,
        "bindings_file_path",
        property(lambda self: path),
    )
    return _writer


@pytest.fixture
def mock_uipath():
    """Patch UiPath() in cli_push to return a mock with resource_catalog + connections.

    cli_push imports `UiPath` lazily from `uipath.platform` inside create_resources,
    so we patch the source module.
    """
    with patch("uipath.platform.UiPath") as mock_cls:
        instance = MagicMock()
        instance.resource_catalog = MagicMock()
        instance.connections = MagicMock()
        mock_cls.return_value = instance
        yield instance


@pytest.fixture
def studio_client():
    from uipath._cli._utils._studio_project import (
        ResourceBuilderMetadataEntry,
        ResourceBuilderMetadataVersion,
    )

    client = MagicMock()
    client.create_referenced_resource = AsyncMock()
    client.create_virtual_resource = AsyncMock()
    supported = ResourceBuilderMetadataVersion(supportsInLineCreation=True)
    # /metadata response — every kind our tests use supports inline creation.
    client.get_resource_builder_metadata = AsyncMock(
        return_value=[
            ResourceBuilderMetadataEntry(kind="asset", versions=[supported]),
            ResourceBuilderMetadataEntry(kind="bucket", versions=[supported]),
            ResourceBuilderMetadataEntry(kind="queue", versions=[supported]),
            ResourceBuilderMetadataEntry(kind="taskCatalog", versions=[supported]),
        ]
    )
    return client


async def _run_create_resources(studio_client):
    from uipath._cli.cli_push import create_resources

    await create_resources(studio_client)


async def test_catalog_hit_calls_referenced_resource_only(
    bindings_file, mock_uipath, studio_client
):
    bindings_file(_make_bindings([_asset_binding(metadata={"SubType": "stringAsset"})]))
    mock_uipath.resource_catalog.list_by_type_async.return_value = _AsyncIterator(
        [_found_resource()]
    )
    studio_client.create_referenced_resource.return_value = SimpleNamespace(
        status=Status.ADDED
    )

    await _run_create_resources(studio_client)

    studio_client.create_referenced_resource.assert_awaited_once()
    studio_client.create_virtual_resource.assert_not_awaited()


async def test_catalog_miss_with_subtype_creates_virtual_with_type(
    bindings_file, mock_uipath, studio_client
):
    bindings_file(_make_bindings([_asset_binding(metadata={"SubType": "stringAsset"})]))
    mock_uipath.resource_catalog.list_by_type_async.return_value = _AsyncIterator([])
    studio_client.create_virtual_resource.return_value = VirtualResourceResult(
        status=Status.ADDED,
    )

    await _run_create_resources(studio_client)

    studio_client.create_virtual_resource.assert_awaited_once()
    req = studio_client.create_virtual_resource.call_args.args[0]
    assert req.kind == "asset"
    assert req.name == "my_asset"
    assert req.type == "stringAsset"
    studio_client.create_referenced_resource.assert_not_awaited()


async def test_catalog_miss_without_subtype_creates_virtual_kind_only(
    bindings_file, mock_uipath, studio_client
):
    bindings_file(_make_bindings([_asset_binding(metadata=None)]))
    mock_uipath.resource_catalog.list_by_type_async.return_value = _AsyncIterator([])
    studio_client.create_virtual_resource.return_value = VirtualResourceResult(
        status=Status.ADDED,
    )

    await _run_create_resources(studio_client)

    studio_client.create_virtual_resource.assert_awaited_once()
    req = studio_client.create_virtual_resource.call_args.args[0]
    assert req.kind == "asset"
    assert req.name == "my_asset"
    assert req.type is None
    # Body that will actually be sent excludes None → no "type" key.
    body = req.model_dump(exclude_none=True)
    assert "type" not in body


async def test_catalog_miss_metadata_without_subtype_key_creates_virtual_kind_only(
    bindings_file, mock_uipath, studio_client
):
    bindings_file(_make_bindings([_asset_binding(metadata={"Other": "x"})]))
    mock_uipath.resource_catalog.list_by_type_async.return_value = _AsyncIterator([])
    studio_client.create_virtual_resource.return_value = VirtualResourceResult(
        status=Status.ADDED,
    )

    await _run_create_resources(studio_client)

    req = studio_client.create_virtual_resource.call_args.args[0]
    assert req.type is None


async def test_unknown_resource_type_skips_catalog_and_creates_virtual(
    bindings_file, mock_uipath, studio_client
):
    """Bindings with a resource kind unknown to ResourceType enum but supported
    by the virtual endpoint (e.g. 'taskCatalog') should skip the resource
    catalog lookup and fall through to the virtual fallback instead of raising
    ValueError."""
    task_catalog_binding = {
        "resource": "taskCatalog",
        "key": "live.good.taskcatalog.Shared",
        "value": {
            "name": {
                "defaultValue": "live.good.taskcatalog",
                "isExpression": False,
                "displayName": "Name",
            },
            "folderPath": {
                "defaultValue": "Shared",
                "isExpression": False,
                "displayName": "Folder Path",
            },
        },
        "metadata": None,
    }
    bindings_file(_make_bindings([task_catalog_binding]))
    studio_client.create_virtual_resource.return_value = VirtualResourceResult(
        status=Status.ADDED,
    )

    await _run_create_resources(studio_client)

    mock_uipath.resource_catalog.list_by_type_async.assert_not_called()
    studio_client.create_virtual_resource.assert_awaited_once()
    req = studio_client.create_virtual_resource.call_args.args[0]
    assert req.kind == "taskCatalog"
    assert req.type is None


async def test_unsupported_virtual_kind_is_skipped_with_warning(
    bindings_file, mock_uipath, studio_client
):
    """Bindings whose kind the virtual endpoint cannot materialize (e.g.
    'entity', 'choiceSet', 'webhook') should be skipped with a warning and
    never reach create_virtual_resource."""
    entity_binding = {
        "resource": "entity",
        "key": "live.good.entity.Shared",
        "value": {
            "name": {
                "defaultValue": "live.good.entity",
                "isExpression": False,
                "displayName": "Name",
            },
            "folderPath": {
                "defaultValue": "Shared",
                "isExpression": False,
                "displayName": "Folder Path",
            },
        },
        "metadata": None,
    }
    bindings_file(_make_bindings([entity_binding]))

    await _run_create_resources(studio_client)

    mock_uipath.resource_catalog.list_by_type_async.assert_not_called()
    studio_client.create_virtual_resource.assert_not_awaited()
    studio_client.create_referenced_resource.assert_not_awaited()


async def test_folder_not_found_falls_back_to_virtual(
    bindings_file, mock_uipath, studio_client
):
    bindings_file(_make_bindings([_asset_binding(metadata={"SubType": "stringAsset"})]))
    mock_uipath.resource_catalog.list_by_type_async.return_value = _AsyncIterator(
        [], raise_exc=FolderNotFoundException("missing folder")
    )
    studio_client.create_virtual_resource.return_value = VirtualResourceResult(
        status=Status.ADDED,
    )

    await _run_create_resources(studio_client)

    studio_client.create_virtual_resource.assert_awaited_once()
    req = studio_client.create_virtual_resource.call_args.args[0]
    assert req.kind == "asset"
    assert req.type == "stringAsset"


async def test_virtual_enriched_exception_caught_and_logged_as_warning(
    bindings_file, mock_uipath, studio_client
):
    bindings_file(
        _make_bindings(
            [
                _asset_binding(name="first"),
                _asset_binding(name="second"),
            ]
        )
    )
    mock_uipath.resource_catalog.list_by_type_async.return_value = _AsyncIterator([])
    # First binding raises, second succeeds → loop must continue past the raise.
    studio_client.create_virtual_resource.side_effect = [
        _enriched_exc(status_code=500, body=b"boom"),
        VirtualResourceResult(status=Status.ADDED),
    ]

    await _run_create_resources(studio_client)

    assert studio_client.create_virtual_resource.await_count == 2


async def test_connection_branch_unchanged_no_virtual_fallback(
    bindings_file, mock_uipath, studio_client
):
    """Connection bindings retain old behavior: retrieve_async + warn on miss, no virtual."""
    connection_binding = {
        "resource": "connection",
        "key": "binding-conn",
        "value": {
            "ConnectionId": {
                "defaultValue": "missing-conn-id",
                "isExpression": False,
                "displayName": "ConnectionId",
            }
        },
        "metadata": {"Connector": "salesforce"},
    }
    bindings_file(_make_bindings([connection_binding]))
    mock_uipath.connections.retrieve_async = AsyncMock(side_effect=_enriched_exc())

    await _run_create_resources(studio_client)

    mock_uipath.connections.retrieve_async.assert_awaited_once()
    studio_client.create_virtual_resource.assert_not_awaited()
    studio_client.create_referenced_resource.assert_not_awaited()


async def test_guardrail_binding_without_folder_path_is_skipped(
    bindings_file, mock_uipath, studio_client
):
    # No folderPath in value → guardrail; should be skipped entirely.
    guardrail_binding = {
        "resource": "asset",
        "key": "binding-guard",
        "value": {
            "name": {
                "defaultValue": "g",
                "isExpression": False,
                "displayName": "name",
            }
        },
        "metadata": None,
    }
    bindings_file(_make_bindings([guardrail_binding]))

    await _run_create_resources(studio_client)

    mock_uipath.resource_catalog.list_by_type_async.assert_not_called()
    studio_client.create_virtual_resource.assert_not_awaited()
    studio_client.create_referenced_resource.assert_not_awaited()


# Ensure env doesn't leak solution ids between tests.
@pytest.fixture(autouse=True)
def _reset_solution_id():
    from uipath.platform.common._config import ConfigurationManager

    ConfigurationManager.studio_solution_id = None
    yield
    ConfigurationManager.studio_solution_id = None


# Set minimal env so UiPath() construction inside create_resources (if not mocked
# away cleanly) doesn't trip on missing creds. The mock_uipath fixture patches
# the class, so this is defense-in-depth.
@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("UIPATH_URL", "https://cloud.uipath.com/org/tenant")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "mock_token")
    yield
    for k in ("UIPATH_URL", "UIPATH_ACCESS_TOKEN"):
        if k in os.environ:
            monkeypatch.delenv(k, raising=False)
