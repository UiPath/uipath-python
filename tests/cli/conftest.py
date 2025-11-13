import os

import pytest

from tests.cli.utils.project_details import ProjectDetails
from tests.cli.utils.uipath_json import UiPathJson


@pytest.fixture
def mock_env_vars(monkeypatch) -> dict[str, str]:
    """Fixture to provide mock environment variables and set them in os.environ."""
    env_vars = {
        "UIPATH_URL": "https://cloud.uipath.com/organization/tenant",
        "UIPATH_TENANT_ID": "e150b32b-8815-4560-8243-055ffc9b7523",
        "UIPATH_ORGANIZATION_ID": "62d19041-d1aa-454d-958d-1375329845dc",
        "UIPATH_ACCESS_TOKEN": "mock_token",
    }
    # Actually set the environment variables using monkeypatch
    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)
    return env_vars


@pytest.fixture
def project_details() -> ProjectDetails:
    if os.path.isfile("mocks/pyproject.toml"):
        with open("mocks/pyproject.toml", "r") as file:
            data = file.read()
    else:
        with open("tests/cli/mocks/pyproject.toml", "r") as file:
            data = file.read()
    return ProjectDetails.from_toml(data)


@pytest.fixture
def uipath_json_legacy(request) -> UiPathJson:
    file_name = (
        "uipath-mock-legacy.json"
        if not hasattr(request, "param") or request.param is None
        else request.param
    )
    if os.path.isfile(f"mocks/{file_name}"):
        with open(f"mocks/{file_name}", "r") as file:
            data = file.read()
    else:
        with open(f"tests/cli/mocks/{file_name}", "r") as file:
            data = file.read()
    return UiPathJson.from_json(data)
