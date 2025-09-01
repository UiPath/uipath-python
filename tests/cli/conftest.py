import pytest


@pytest.fixture
def mock_env_vars() -> dict[str, str]:
    """Fixture to provide mock environment variables."""
    return {
        "UIPATH_URL": "https://cloud.uipath.com/organization/tenant",
        "UIPATH_TENANT_ID": "e150b32b-8815-4560-8243-055ffc9b7523",
        "UIPATH_ORGANIZATION_ID": "62d19041-d1aa-454d-958d-1375329845dc",
        "UIPATH_ACCESS_TOKEN": "mock_token",
    }
