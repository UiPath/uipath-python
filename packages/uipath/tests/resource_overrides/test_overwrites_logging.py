# type: ignore
"""Tests for INFO-level diagnostic logging on the resource-overwrites read paths.

Covers the recent change that surfaces bindings.json content and raw resource
overwrites (from both uipath.json and the Studio API) at INFO so binding/
overwrite mismatches can be diagnosed from logs alone.
"""

import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from uipath._cli._utils._common import read_resource_overwrites_from_file
from uipath._cli._utils._studio_project import StudioClient
from uipath.platform.common import GenericResourceOverwrite

_VALID_OVERWRITES = {
    "asset.asset_name": {
        "name": "Overwritten Asset Name",
        "folderPath": "Overwritten/Asset/Folder",
    },
    "bucket.bucket_name": {
        "name": "Overwritten Bucket Name",
        "folderPath": "Overwritten/Bucket/Folder",
    },
}


def _write_uipath_json(directory: Path, overwrites: dict) -> Path:
    config_path = directory / "uipath.json"
    config_path.write_text(
        json.dumps(
            {
                "runtime": {"internalArguments": {"resourceOverwrites": overwrites}},
            }
        )
    )
    return config_path


class TestReadResourceOverwritesFromFileLogging:
    """Behavior: read_resource_overwrites_from_file logs diagnostic info at INFO."""

    async def test_logs_raw_overwrites_at_info_when_file_present(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        config_path = _write_uipath_json(tmp_path, _VALID_OVERWRITES)

        with caplog.at_level(logging.INFO, logger="uipath._cli._utils._common"):
            result = await read_resource_overwrites_from_file(str(tmp_path))

        assert set(result.keys()) == set(_VALID_OVERWRITES.keys())

        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert any(
            "Resource overwrites read from" in r.getMessage()
            and str(config_path) in r.getMessage()
            and f"({len(_VALID_OVERWRITES)} entries)" in r.getMessage()
            for r in info_records
        ), f"expected INFO log with file path and entry count, got: {caplog.text}"

        # The raw JSON payload should be present in the log so a developer can
        # diff it against what Studio later returns.
        assert "Overwritten Asset Name" in caplog.text
        assert "Overwritten Bucket Name" in caplog.text

    async def test_logs_info_when_config_file_missing(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        # tmp_path is empty — no uipath.json present.
        missing_dir = tmp_path / "does-not-exist"
        missing_dir.mkdir()

        with caplog.at_level(logging.INFO, logger="uipath._cli._utils._common"):
            result = await read_resource_overwrites_from_file(str(missing_dir))

        assert result == {}
        info_messages = [
            r.getMessage() for r in caplog.records if r.levelno == logging.INFO
        ]
        assert any(
            "Resource overwrites config file not found" in msg for msg in info_messages
        ), f"expected INFO log for missing config, got: {info_messages}"

    async def test_logs_warning_when_json_is_malformed(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        (tmp_path / "uipath.json").write_text("{not valid json")

        with caplog.at_level(logging.WARNING, logger="uipath._cli._utils._common"):
            result = await read_resource_overwrites_from_file(str(tmp_path))

        assert result == {}
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert any(
            "Failed to parse resource overwrites" in r.getMessage() for r in warnings
        )

    async def test_unrecognized_overwrite_key_is_skipped_with_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        overwrites = {
            **_VALID_OVERWRITES,
            "totallyUnknownKind.foo": {"name": "x", "folderPath": "y"},
        }
        _write_uipath_json(tmp_path, overwrites)

        with caplog.at_level(logging.WARNING, logger="uipath._cli._utils._common"):
            result = await read_resource_overwrites_from_file(str(tmp_path))

        # Valid entries still parsed; unknown key dropped.
        assert set(result.keys()) == set(_VALID_OVERWRITES.keys())
        assert any(
            "Skipping unrecognized resource overwrite" in r.getMessage()
            and "totallyUnknownKind.foo" in r.getMessage()
            for r in caplog.records
            if r.levelno == logging.WARNING
        )


class TestStudioClientGetResourceOverwritesLogging:
    """Behavior: StudioClient.get_resource_overwrites logs bindings + raw payload."""

    @pytest.fixture
    def studio_client(self) -> StudioClient:
        # Inject a mock UiPath so no real HTTP setup is required.
        mock_uipath = MagicMock()
        mock_uipath.api_client.request_async = AsyncMock()
        client = StudioClient(project_id="test-project-id", uipath=mock_uipath)
        # Avoid the network call that resolves the solution id.
        client._get_solution_id = AsyncMock(return_value="test-solution-id")  # type: ignore[method-assign]
        return client

    async def test_warns_and_returns_empty_when_bindings_file_missing(
        self,
        studio_client: StudioClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        from uipath.platform.common._config import ConfigurationManager

        missing_path = tmp_path / "bindings.json"
        monkeypatch.setattr(
            ConfigurationManager,
            "bindings_file_path",
            property(lambda self: missing_path),
        )

        with caplog.at_level(logging.WARNING):
            result = await studio_client.get_resource_overwrites()

        assert result == {}
        assert any(
            "Bindings file not found" in r.getMessage()
            for r in caplog.records
            if r.levelno == logging.WARNING
        )
        # No request should have been made when there is nothing to upload.
        studio_client.uipath.api_client.request_async.assert_not_called()

    async def test_logs_bindings_content_and_received_overwrites_at_info(
        self,
        studio_client: StudioClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        from uipath.platform.common._config import ConfigurationManager

        bindings_path = tmp_path / "bindings.json"
        bindings_content = json.dumps(
            {"version": "2", "resources": [{"name": "my_bucket", "kind": "bucket"}]}
        )
        bindings_path.write_text(bindings_content)
        monkeypatch.setattr(
            ConfigurationManager,
            "bindings_file_path",
            property(lambda self: bindings_path),
        )
        monkeypatch.delenv("UIPATH_TENANT_ID", raising=False)

        response = MagicMock()
        response.json.return_value = {
            "bucket.my_bucket": {
                "name": "prod_bucket",
                "folderPath": "Prod/Folder",
            }
        }
        studio_client.uipath.api_client.request_async = AsyncMock(return_value=response)

        with caplog.at_level(logging.INFO, logger="uipath._cli._utils._studio_project"):
            result = await studio_client.get_resource_overwrites()

        # Returned dict is parsed via ResourceOverwriteParser.
        assert set(result.keys()) == {"bucket.my_bucket"}

        info_text = "\n".join(
            r.getMessage() for r in caplog.records if r.levelno == logging.INFO
        )
        # Bindings content is logged so we can compare what was sent to Studio.
        assert "Resource bindings" in info_text
        assert "my_bucket" in info_text
        # Received overwrites payload is logged with the solution id and count.
        assert "Resource overwrites received for solution test-solution-id" in info_text
        assert "(1 entries)" in info_text
        assert "prod_bucket" in info_text

    async def test_parses_received_overwrites_into_resource_overwrite_objects(
        self,
        studio_client: StudioClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from uipath.platform.common._config import ConfigurationManager

        bindings_path = tmp_path / "bindings.json"
        bindings_path.write_text("{}")
        monkeypatch.setattr(
            ConfigurationManager,
            "bindings_file_path",
            property(lambda self: bindings_path),
        )

        response = MagicMock()
        response.json.return_value = {
            "bucket.my_bucket": {
                "name": "prod_bucket",
                "folderPath": "Prod/Folder",
            }
        }
        studio_client.uipath.api_client.request_async = AsyncMock(return_value=response)

        result = await studio_client.get_resource_overwrites()

        parsed = result["bucket.my_bucket"]
        assert isinstance(parsed, GenericResourceOverwrite)
        assert parsed.resource_identifier == "prod_bucket"
        assert parsed.folder_identifier == "Prod/Folder"

    async def test_passes_tenant_id_header_from_environment(
        self,
        studio_client: StudioClient,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from uipath.platform.common._config import ConfigurationManager

        bindings_path = tmp_path / "bindings.json"
        bindings_path.write_text("{}")
        monkeypatch.setattr(
            ConfigurationManager,
            "bindings_file_path",
            property(lambda self: bindings_path),
        )
        monkeypatch.setenv("UIPATH_TENANT_ID", "tenant-from-env")

        response = MagicMock()
        response.json.return_value = {}
        request_mock = AsyncMock(return_value=response)
        studio_client.uipath.api_client.request_async = request_mock

        await studio_client.get_resource_overwrites()

        # The header carrying the tenant id should reflect the env var value.
        call_kwargs = request_mock.await_args.kwargs
        headers = call_kwargs["headers"]
        assert any(value == "tenant-from-env" for value in headers.values()), headers
