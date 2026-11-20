"""A UiPath() configured from the environment re-reads the token on every request."""

from unittest.mock import patch

import pytest
from pytest_httpx import HTTPXMock

from uipath.platform import UiPath, UiPathApiConfig
from uipath.platform.common import ApiClient
from uipath.platform.common._base_service import BaseService
from uipath.platform.common.auth import TokenData

UNATTENDED = "UNATTENDED_USER_ACCESS_TOKEN"
ACCESS = "UIPATH_ACCESS_TOKEN"
URL = "https://cloud.uipath.com/org/tenant"


@pytest.fixture
def url(base_url: str, org: str, tenant: str) -> str:
    return f"{base_url}{org}{tenant}/endpoint"


@pytest.fixture
def env_config(config: UiPathApiConfig, monkeypatch) -> UiPathApiConfig:
    """The fixture config, flagged as UiPath() flags one built from the environment."""
    monkeypatch.setenv(ACCESS, config.secret)
    monkeypatch.delenv(UNATTENDED, raising=False)
    config.secret_from_environment = True
    return config


def _sent_auth(httpx_mock: HTTPXMock) -> list[str]:
    return [request.headers["Authorization"] for request in httpx_mock.get_requests()]


class TestEnvironmentSecret:
    def test_each_request_reads_the_current_environment_token(
        self,
        httpx_mock: HTTPXMock,
        env_config,
        execution_context,
        url,
        monkeypatch,
        secret,
    ):
        httpx_mock.add_response(url=url, status_code=200, json={})
        httpx_mock.add_response(url=url, status_code=200, json={})
        service = BaseService(config=env_config, execution_context=execution_context)

        service.request("GET", "/endpoint")
        monkeypatch.setenv(ACCESS, "renewed")
        service.request("GET", "/endpoint")

        assert _sent_auth(httpx_mock) == [f"Bearer {secret}", "Bearer renewed"]
        assert env_config.secret == "renewed"

    @pytest.mark.anyio
    async def test_each_async_request_reads_the_current_environment_token(
        self,
        httpx_mock: HTTPXMock,
        env_config,
        execution_context,
        url,
        monkeypatch,
        secret,
    ):
        httpx_mock.add_response(url=url, status_code=200, json={})
        httpx_mock.add_response(url=url, status_code=200, json={})
        service = BaseService(config=env_config, execution_context=execution_context)

        await service.request_async("GET", "/endpoint")
        monkeypatch.setenv(ACCESS, "renewed")
        await service.request_async("GET", "/endpoint")

        assert _sent_auth(httpx_mock) == [f"Bearer {secret}", "Bearer renewed"]
        assert env_config.secret == "renewed"

    def test_the_unattended_token_wins_over_the_access_token(
        self, httpx_mock: HTTPXMock, env_config, execution_context, url, monkeypatch
    ):
        httpx_mock.add_response(url=url, status_code=200, json={})
        monkeypatch.setenv(UNATTENDED, "unattended")
        monkeypatch.setenv(ACCESS, "access")
        service = BaseService(config=env_config, execution_context=execution_context)

        service.request("GET", "/endpoint")

        assert _sent_auth(httpx_mock) == ["Bearer unattended"]

    def test_a_missing_variable_falls_back_to_the_stored_secret(
        self,
        httpx_mock: HTTPXMock,
        env_config,
        execution_context,
        url,
        monkeypatch,
        secret,
    ):
        httpx_mock.add_response(url=url, status_code=200, json={})
        service = BaseService(config=env_config, execution_context=execution_context)
        monkeypatch.delenv(ACCESS)

        service.request("GET", "/endpoint")

        assert _sent_auth(httpx_mock) == [f"Bearer {secret}"]

    def test_a_caller_supplied_authorization_header_is_left_alone(
        self, httpx_mock: HTTPXMock, env_config, execution_context, url, monkeypatch
    ):
        httpx_mock.add_response(url=url, status_code=200, json={})
        monkeypatch.setenv(ACCESS, "renewed")
        service = BaseService(config=env_config, execution_context=execution_context)

        service.request("GET", "/endpoint", headers={"authorization": "Bearer mine"})

        assert _sent_auth(httpx_mock) == ["Bearer mine"]

    def test_the_callers_headers_mapping_is_not_modified(
        self, httpx_mock: HTTPXMock, env_config, execution_context, url
    ):
        httpx_mock.add_response(url=url, status_code=200, json={})
        service = BaseService(config=env_config, execution_context=execution_context)
        headers = {"X-Test": "1"}

        service.request("GET", "/endpoint", headers=headers)

        assert headers == {"X-Test": "1"}
        assert httpx_mock.get_requests()[0].headers["X-Test"] == "1"

    def test_api_client_folder_headers_do_not_pin_the_old_token(
        self, httpx_mock: HTTPXMock, env_config, execution_context, url, monkeypatch
    ):
        """include_folder_headers used to copy the client defaults, Authorization included."""
        monkeypatch.setenv("UIPATH_FOLDER_KEY", "folder-1")
        httpx_mock.add_response(url=url, status_code=200, json={})
        client = ApiClient(env_config, execution_context)
        monkeypatch.setenv(ACCESS, "renewed")

        client.request("GET", "/endpoint", include_folder_headers=True)

        sent = httpx_mock.get_requests()[0]
        assert sent.headers["Authorization"] == "Bearer renewed"
        assert sent.headers["x-uipath-folderkey"] == "folder-1"
        assert sent.headers["Accept"] == "application/json"


class TestStaticSecret:
    def test_an_explicit_secret_ignores_the_environment(
        self, httpx_mock: HTTPXMock, config, execution_context, url, monkeypatch, secret
    ):
        httpx_mock.add_response(url=url, status_code=200, json={})
        monkeypatch.setenv(ACCESS, "renewed")
        service = BaseService(config=config, execution_context=execution_context)

        service.request("GET", "/endpoint")

        assert config.secret_from_environment is False
        assert _sent_auth(httpx_mock) == [f"Bearer {secret}"]
        assert config.secret == secret

    def test_the_flag_defaults_to_false(self):
        assert (
            UiPathApiConfig(base_url="https://x", secret="s").secret_from_environment
            is False
        )
        assert (
            UiPathApiConfig(
                base_url="https://x", secret="s", secret_from_environment=True
            ).secret_from_environment
            is True
        )


class TestUiPathFactory:
    def test_a_client_built_from_the_environment_follows_it(self, monkeypatch):
        monkeypatch.setenv("UIPATH_URL", URL)
        monkeypatch.setenv(ACCESS, "env-token")
        monkeypatch.delenv(UNATTENDED, raising=False)
        sdk = UiPath()
        assert sdk._config.secret_from_environment is True
        assert sdk._config.secret == "env-token"

        monkeypatch.setenv(ACCESS, "renewed")

        assert sdk.api_client.default_headers["Authorization"] == "Bearer renewed"
        assert sdk._config.secret == "renewed"

    def test_an_explicit_secret_does_not(self, monkeypatch):
        monkeypatch.setenv("UIPATH_URL", URL)
        monkeypatch.setenv(ACCESS, "env-token")

        sdk = UiPath(secret="mine")
        monkeypatch.setenv(ACCESS, "renewed")

        assert sdk._config.secret_from_environment is False
        assert sdk.api_client.default_headers["Authorization"] == "Bearer mine"

    def test_client_credentials_do_not(self, monkeypatch):
        monkeypatch.setenv(ACCESS, "env-token")
        with patch(
            "uipath.platform._uipath.ExternalApplicationService.get_token_data",
            return_value=TokenData(access_token="app-token"),
        ):
            sdk = UiPath(base_url=URL, client_id="app", client_secret="s3cret")

        assert sdk._config.secret_from_environment is False
        assert sdk._config.secret == "app-token"
