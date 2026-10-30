"""Per-entry behaviour of ``StudioClient.get_resource_overwrites``.

``uipath debug`` and ``uipath eval`` load their resource overwrites from the
Studio backend when ``UIPATH_PROJECT_ID`` is set. One entry of a kind this SDK
does not know must not fail the whole run.
"""

import json
import logging
from pathlib import Path

import pytest
from pytest_httpx import HTTPXMock

from uipath._cli._utils._studio_project import StudioClient
from uipath.platform.common import GenericResourceOverwrite, UiPathConfig

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
