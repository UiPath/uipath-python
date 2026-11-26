"""Per-entry behaviour of ``StudioClient.get_resource_overwrites``.

``uipath debug`` and ``uipath eval`` load their resource overwrites from the
Studio backend when ``UIPATH_PROJECT_ID`` is set. One entry of a kind this SDK
does not know must not fail the whole run; a malformed entry of a known kind
still does.
"""

import json
import logging
from pathlib import Path

import pytest
from pydantic import ValidationError
from pytest_httpx import HTTPXMock

from uipath._cli._utils._studio_project import StudioClient
from uipath.platform.common import (
    ConnectionResourceOverwrite,
    GenericResourceOverwrite,
    UiPathConfig,
)

_ORG_URL = "https://cloud.uipath.com/organization"
_PROJECT_ID = "test-project-id"
_SOLUTION_ID = "test-solution-id"
_OVERWRITES_URL = (
    f"{_ORG_URL}/studio_/backend/api/resourcebuilder/{_SOLUTION_ID}/binding-overwrites"
)
_LOGGER_NAME = "uipath._cli._utils._studio_project"


@pytest.fixture
def studio_logs(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> pytest.LogCaptureFixture:
    """Records reach caplog's root handler whatever state CLI tests left the loggers in.

    Tests that invoke the Click CLI leave the ``uipath`` loggers, the module
    logger included, with ``propagate = False``. Re-enable propagation along
    the whole chain for this test only; the handler stays on root, so each
    record is captured exactly once.
    """
    logger: logging.Logger | None = logging.getLogger(_LOGGER_NAME)
    while logger is not None:
        monkeypatch.setattr(logger, "propagate", True)
        logger = logger.parent
    caplog.set_level(logging.WARNING, logger=_LOGGER_NAME)
    return caplog


@pytest.fixture
def studio_client(
    mock_env_vars: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> StudioClient:
    """A client over a real ``UiPath`` whose solution id is already cached.

    ``UiPathConfig.bindings_file_path`` is relative to the working directory,
    so the test runs from ``tmp_path`` with a ``bindings.json`` in it.
    """
    monkeypatch.chdir(tmp_path)
    (tmp_path / "bindings.json").write_text(
        json.dumps({"version": "2", "resources": []})
    )
    monkeypatch.setattr(UiPathConfig, "studio_solution_id", _SOLUTION_ID)
    return StudioClient(project_id=_PROJECT_ID)


async def test_get_resource_overwrites_skips_unknown_entries(
    studio_client: StudioClient,
    httpx_mock: HTTPXMock,
    studio_logs: pytest.LogCaptureFixture,
) -> None:
    httpx_mock.add_response(
        method="POST",
        url=_OVERWRITES_URL,
        json={
            "asset.A": {"name": "B", "folderPath": "F"},
            "weird.X": {"foo": 1},
        },
    )

    overwrites = await studio_client.get_resource_overwrites()

    assert set(overwrites) == {"asset.A"}
    asset = overwrites["asset.A"]
    assert isinstance(asset, GenericResourceOverwrite)
    assert asset.resource_identifier == "B"
    assert asset.folder_identifier == "F"
    warnings = [
        r.getMessage() for r in studio_logs.records if r.levelno == logging.WARNING
    ]
    skipped = [message for message in warnings if "weird.X" in message]
    assert len(skipped) == 1, warnings
    assert "\n" not in skipped[0], skipped[0]


async def test_get_resource_overwrites_raises_for_a_malformed_known_kind(
    studio_client: StudioClient, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        method="POST",
        url=_OVERWRITES_URL,
        json={"asset.A": {"name": "B"}, "weird.X": {"foo": 1}},
    )

    with pytest.raises(ValidationError):
        await studio_client.get_resource_overwrites()


@pytest.fixture
def debug_job_config(tmp_path: Path, studio_client: StudioClient):
    """Writes the config file of a debug job, read from the working directory."""

    def write(fps_properties: dict[str, str]) -> None:
        (tmp_path / UiPathConfig.config_file_name).write_text(
            json.dumps({"fpsProperties": fps_properties})
        )
        UiPathConfig.reset()

    yield write
    UiPathConfig.reset()


async def test_get_resource_overwrites_uses_the_ones_the_debug_job_carries(
    studio_client: StudioClient, debug_job_config, httpx_mock: HTTPXMock
) -> None:
    debug_job_config(
        {
            "debug.executor": json.dumps(
                {
                    "projectId": _PROJECT_ID,
                    "resourceOverwrites": {
                        "asset.A": {"name": "B", "folderPath": "F"},
                    },
                }
            )
        }
    )

    overwrites = await studio_client.get_resource_overwrites()

    asset = overwrites["asset.A"]
    assert isinstance(asset, GenericResourceOverwrite)
    assert asset.resource_identifier == "B"
    assert asset.folder_identifier == "F"
    # Studio is not asked: neither for the overwrites nor for the solution id.
    assert httpx_mock.get_requests() == []


async def test_get_resource_overwrites_respells_the_kinds_the_debug_job_carries(
    studio_client: StudioClient, debug_job_config, httpx_mock: HTTPXMock
) -> None:
    debug_job_config(
        {
            "debug.executor": json.dumps(
                {
                    "projectId": _PROJECT_ID,
                    "resourceOverwrites": {
                        "Connection.c-1": {"ConnectionId": "robot", "folderKey": "k"},
                        "Connection.c-2": {"ConnectionId": "other", "folderKey": "k"},
                        "connection.c-2": {"connectionId": "own", "folderKey": "k"},
                        "Asset.A": {"name": "B", "folderPath": "F"},
                    },
                }
            )
        }
    )

    overwrites = await studio_client.get_resource_overwrites()

    assert sorted(overwrites) == ["asset.A", "connection.c-1", "connection.c-2"]
    respelled = overwrites["connection.c-1"]
    assert isinstance(respelled, ConnectionResourceOverwrite)
    assert respelled.resource_identifier == "robot"
    # The entry already in this SDK's spelling wins, wherever it sits in the job.
    assert overwrites["connection.c-2"].resource_identifier == "own"
    assert httpx_mock.get_requests() == []


async def test_get_resource_overwrites_skips_unknown_entries_the_debug_job_carries(
    studio_client: StudioClient,
    debug_job_config,
    studio_logs: pytest.LogCaptureFixture,
) -> None:
    debug_job_config(
        {
            "debug.executor": json.dumps(
                {
                    "resourceOverwrites": {
                        "asset.A": {"name": "B", "folderPath": "F"},
                        "weird.X": {"foo": 1},
                    }
                }
            )
        }
    )

    overwrites = await studio_client.get_resource_overwrites()

    assert set(overwrites) == {"asset.A"}
    warnings = [
        r.getMessage() for r in studio_logs.records if r.levelno == logging.WARNING
    ]
    assert [message for message in warnings if "weird.X" in message] == [
        "Skipping resource overwrite 'weird.X' from the debug job: unknown kind 'weird'"
    ]


async def test_get_resource_overwrites_asks_studio_when_the_debug_job_carries_none(
    studio_client: StudioClient, debug_job_config, httpx_mock: HTTPXMock
) -> None:
    debug_job_config({"debug.executor": json.dumps({"projectId": _PROJECT_ID})})
    # The fixture's reset dropped the cached solution id the client asks under.
    UiPathConfig.studio_solution_id = _SOLUTION_ID
    httpx_mock.add_response(
        method="POST",
        url=_OVERWRITES_URL,
        json={"asset.A": {"name": "B", "folderPath": "F"}},
    )

    overwrites = await studio_client.get_resource_overwrites()

    assert set(overwrites) == {"asset.A"}
