"""Tests for AuthSession (refresh_access_token and ensure_valid_token)."""

import os
import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from uipath._cli._auth._auth_service import AuthService
from uipath._cli._auth._auth_session import AuthSession
from uipath.platform.common import TokenData
from uipath.runtime.errors import UiPathRuntimeError


@pytest.fixture
def mock_auth_config():
    return {
        "client_id": "test_client_id",
        "port": 8104,
        "redirect_uri": "http://localhost:8104/callback",
        "scope": "openid profile offline_access",
    }


@pytest.fixture
def sample_token_data():
    return TokenData(
        access_token="new_access_token_123",
        refresh_token="new_refresh_token_456",
        expires_in=3600,
        token_type="Bearer",
        scope="openid profile offline_access",
        id_token="id_token_789",
    )


class TestAuthSessionRefreshToken:
    @pytest.mark.parametrize(
        "environment, expected_domain",
        [
            ("cloud", "https://cloud.uipath.com"),
            ("alpha", "https://alpha.uipath.com"),
            ("staging", "https://staging.uipath.com"),
        ],
    )
    async def test_refresh_different_domains(
        self, environment, expected_domain, mock_auth_config, sample_token_data
    ):
        with (
            patch(
                "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                new_callable=AsyncMock,
                return_value=mock_auth_config,
            ),
            patch(
                "uipath._cli._auth._auth_session.IdentityService.refresh_access_token_async",
                new_callable=AsyncMock,
                return_value=sample_token_data,
            ) as mock_refresh,
        ):
            auth_service = AuthService(environment=environment, force=False)
            auth_session = AuthSession(auth_service._domain)
            result = await auth_session.refresh_access_token("test_refresh_token")

            mock_refresh.assert_called_once_with(
                refresh_token="test_refresh_token",
                client_id=mock_auth_config["client_id"],
            )
            assert auth_session._identity_service._domain == expected_domain
            assert result.access_token == sample_token_data.access_token
            assert result.refresh_token == sample_token_data.refresh_token

    @pytest.mark.parametrize(
        "env_var_url, environment, expected_domain",
        [
            (
                "https://custom.automationsuite.org/org/tenant",
                None,
                "https://custom.automationsuite.org",
            ),
            (
                "https://mycompany.uipath.com/org/tenant/",
                None,
                "https://mycompany.uipath.com",
            ),
            (
                "https://custom.automationsuite.org/org/tenant",
                "alpha",
                "https://alpha.uipath.com",
            ),
            (
                "https://custom.automationsuite.org/org/tenant",
                "staging",
                "https://staging.uipath.com",
            ),
            (
                "https://custom.automationsuite.org/org/tenant",
                "cloud",
                "https://cloud.uipath.com",
            ),
        ],
    )
    async def test_refresh_with_uipath_url_env(
        self,
        env_var_url,
        environment,
        expected_domain,
        mock_auth_config,
        sample_token_data,
    ):
        original_env = os.environ.get("UIPATH_URL")
        os.environ["UIPATH_URL"] = env_var_url

        try:
            with (
                patch(
                    "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                    new_callable=AsyncMock,
                    return_value=mock_auth_config,
                ),
                patch(
                    "uipath._cli._auth._auth_session.IdentityService.refresh_access_token_async",
                    new_callable=AsyncMock,
                    return_value=sample_token_data,
                ) as mock_refresh,
            ):
                auth_service = AuthService(environment=environment, force=False)
                auth_session = AuthSession(auth_service._domain)
                result = await auth_session.refresh_access_token("test_refresh_token")

                mock_refresh.assert_called_once_with(
                    refresh_token="test_refresh_token",
                    client_id=mock_auth_config["client_id"],
                )
                assert auth_session._identity_service._domain == expected_domain
                assert result.access_token == sample_token_data.access_token
                assert result.refresh_token == sample_token_data.refresh_token

        finally:
            if original_env is not None:
                os.environ["UIPATH_URL"] = original_env
            elif "UIPATH_URL" in os.environ:
                del os.environ["UIPATH_URL"]

    async def test_refresh_unauthorized(self, mock_auth_config):
        import httpx

        mock_response = Mock()
        mock_response.status_code = 401
        error = httpx.HTTPStatusError(
            "unauthorized", request=Mock(), response=mock_response
        )

        with (
            patch(
                "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                new_callable=AsyncMock,
                return_value=mock_auth_config,
            ),
            patch(
                "uipath._cli._auth._auth_session.IdentityService.refresh_access_token_async",
                new_callable=AsyncMock,
                side_effect=error,
            ),
            patch("uipath._cli._auth._auth_session.ConsoleLogger") as mock_logger_cls,
        ):
            mock_console = Mock()
            mock_console.error.side_effect = SystemExit(1)
            mock_logger_cls.return_value = mock_console

            auth_service = AuthService(environment="cloud", force=False)
            auth_session = AuthSession(auth_service._domain)

            with pytest.raises((SystemExit, Exception)):
                await auth_session.refresh_access_token("test_refresh_token")

            mock_console.error.assert_called_once_with("Unauthorized")

    async def test_refresh_server_error(self, mock_auth_config):
        import httpx

        mock_response = Mock()
        mock_response.status_code = 500
        error = httpx.HTTPStatusError(
            "server error", request=Mock(), response=mock_response
        )

        with (
            patch(
                "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                new_callable=AsyncMock,
                return_value=mock_auth_config,
            ),
            patch(
                "uipath._cli._auth._auth_session.IdentityService.refresh_access_token_async",
                new_callable=AsyncMock,
                side_effect=error,
            ),
            patch("uipath._cli._auth._auth_session.ConsoleLogger") as mock_logger_cls,
        ):
            mock_console = Mock()
            mock_console.error.side_effect = SystemExit(1)
            mock_logger_cls.return_value = mock_console

            auth_service = AuthService(environment="cloud", force=False)
            auth_session = AuthSession(auth_service._domain)

            with pytest.raises((SystemExit, Exception)):
                await auth_session.refresh_access_token("test_refresh_token")

            mock_console.error.assert_called_once_with("Failed to refresh token: 500")

    async def test_refresh_success_response_format(
        self, mock_auth_config, sample_token_data
    ):
        with (
            patch(
                "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                new_callable=AsyncMock,
                return_value=mock_auth_config,
            ),
            patch(
                "uipath._cli._auth._auth_session.IdentityService.refresh_access_token_async",
                new_callable=AsyncMock,
                return_value=sample_token_data,
            ),
        ):
            auth_service = AuthService(environment="cloud", force=False)
            auth_session = AuthSession(auth_service._domain)
            result = await auth_session.refresh_access_token("test_refresh_token")

            assert result.access_token is not None
            assert result.refresh_token is not None
            assert result.expires_in is not None
            assert result.token_type is not None
            assert result.scope is not None
            assert result.id_token is not None
            assert result.access_token == sample_token_data.access_token
            assert result.refresh_token == sample_token_data.refresh_token

    async def test_refresh_malformed_domain_handling(
        self, mock_auth_config, sample_token_data
    ):
        test_cases = [
            ("https://example.uipath.com/", None, "https://example.uipath.com"),
            ("https://example.com/", "example", "https://example.uipath.com"),
            (
                "https://example.com/some/path",
                "example",
                "https://example.uipath.com",
            ),
        ]

        for uipath_url, environment, expected_domain in test_cases:
            with (
                patch(
                    "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                    new_callable=AsyncMock,
                    return_value=mock_auth_config,
                ),
                patch(
                    "uipath._cli._auth._auth_session.IdentityService.refresh_access_token_async",
                    new_callable=AsyncMock,
                    return_value=sample_token_data,
                ),
            ):
                os.environ["UIPATH_URL"] = uipath_url
                auth_service = AuthService(environment=environment, force=False)
                auth_session = AuthSession(auth_service._domain)
                await auth_session.refresh_access_token("test_refresh_token")

                assert auth_session._identity_service._domain == expected_domain

    @pytest.mark.parametrize(
        "scenario_name, env_vars, environment, expected_domain",
        [
            (
                "refresh_with_uipath_url_env_variable",
                {"UIPATH_URL": "https://custom.automationsuite.org/org/tenant"},
                None,
                "https://custom.automationsuite.org",
            ),
            (
                "refresh_with_uipath_url_env_variable_with_trailing_slash",
                {"UIPATH_URL": "https://custom.uipath.com/org/tenant/"},
                None,
                "https://custom.uipath.com",
            ),
            (
                "refresh_with_alpha_flag_overrides_env",
                {"UIPATH_URL": "https://custom.uipath.com/org/tenant"},
                "alpha",
                "https://alpha.uipath.com",
            ),
            (
                "refresh_with_staging_flag_overrides_env",
                {"UIPATH_URL": "https://custom.uipath.com/org/tenant"},
                "staging",
                "https://staging.uipath.com",
            ),
            (
                "refresh_with_cloud_flag_overrides_env",
                {"UIPATH_URL": "https://custom.uipath.com/org/tenant"},
                "cloud",
                "https://cloud.uipath.com",
            ),
            (
                "refresh_default_to_cloud",
                {},
                None,
                "https://cloud.uipath.com",
            ),
        ],
    )
    async def test_refresh_auth_scenarios_integration(
        self,
        scenario_name,
        env_vars,
        environment,
        expected_domain,
        mock_auth_config,
        sample_token_data,
    ):
        original_env_vars = {}
        for key in env_vars:
            original_env_vars[key] = os.environ.get(key)

        try:
            for key, value in env_vars.items():
                os.environ[key] = value

            with (
                patch(
                    "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                    new_callable=AsyncMock,
                    return_value=mock_auth_config,
                ),
                patch(
                    "uipath._cli._auth._auth_session.IdentityService.refresh_access_token_async",
                    new_callable=AsyncMock,
                    return_value=sample_token_data,
                ) as mock_refresh,
            ):
                auth_service = AuthService(environment=environment, force=False)
                auth_session = AuthSession(auth_service._domain)
                result = await auth_session.refresh_access_token("test_refresh_token")

                mock_refresh.assert_called_once_with(
                    refresh_token="test_refresh_token",
                    client_id=mock_auth_config["client_id"],
                )
                assert auth_session._identity_service._domain == expected_domain
                assert result.access_token == sample_token_data.access_token
                assert result.refresh_token == sample_token_data.refresh_token

        finally:
            for key, original_value in original_env_vars.items():
                if original_value is not None:
                    os.environ[key] = original_value
                elif key in os.environ:
                    del os.environ[key]


class TestAuthSessionEnsureValidToken:
    @pytest.mark.parametrize(
        "domain, expected_domain",
        [
            ("https://cloud.uipath.com", "https://cloud.uipath.com"),
            ("https://alpha.uipath.com", "https://alpha.uipath.com"),
            ("https://staging.uipath.com", "https://staging.uipath.com"),
            (
                "https://custom.automationsuite.org",
                "https://custom.automationsuite.org",
            ),
        ],
    )
    async def test_ensure_valid_token_refresh_flow_different_domains(
        self,
        domain,
        expected_domain,
        mock_auth_config,
        sample_token_data,
    ):
        expired_auth_data = {
            "access_token": "old_access_token",
            "refresh_token": "valid_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "openid profile offline_access",
            "id_token": "old_id_token",
        }

        past_time = time.time() - 3600
        expired_token_claims = {"exp": past_time, "prt_id": "test_prt_id"}

        with (
            patch(
                "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                new_callable=AsyncMock,
                return_value=mock_auth_config,
            ),
            patch(
                "uipath._cli._auth._auth_session.get_auth_data",
                return_value=TokenData.model_validate(expired_auth_data),
            ),
            patch(
                "uipath._cli._auth._auth_session.get_parsed_token_data",
                return_value=expired_token_claims,
            ),
            patch(
                "uipath._cli._auth._auth_session.update_auth_file"
            ) as mock_update_auth,
            patch("uipath._cli._auth._auth_session.update_env_file"),
            patch(
                "uipath._cli._auth._auth_session.IdentityService.refresh_access_token_async",
                new_callable=AsyncMock,
                return_value=sample_token_data,
            ) as mock_refresh,
        ):
            auth_session = AuthSession(domain)
            await auth_session.ensure_valid_token()

            mock_refresh.assert_called_once_with(
                refresh_token=expired_auth_data["refresh_token"],
                client_id=mock_auth_config["client_id"],
            )
            assert auth_session._identity_service._domain == expected_domain
            mock_update_auth.assert_called_once()
            call_args = mock_update_auth.call_args[0][0]
            assert call_args.access_token == sample_token_data.access_token

    async def test_ensure_valid_token_skips_refresh_when_not_expired(
        self, mock_auth_config
    ):
        future_time = time.time() + 3600
        valid_auth_data = {
            "access_token": "valid_access_token",
            "refresh_token": "valid_refresh_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "openid profile offline_access",
            "id_token": "valid_id_token",
            "exp": future_time,
        }

        with (
            patch(
                "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                new_callable=AsyncMock,
                return_value=mock_auth_config,
            ),
            patch(
                "uipath._cli._auth._auth_session.get_auth_data",
                return_value=TokenData.model_validate(valid_auth_data),
            ),
            patch(
                "uipath._cli._auth._auth_session.get_parsed_token_data",
                return_value=valid_auth_data,
            ),
            patch(
                "uipath._cli._auth._auth_session.IdentityService.refresh_access_token_async",
                new_callable=AsyncMock,
            ) as mock_refresh,
            patch("uipath._cli._auth._auth_session.update_auth_file"),
            patch("uipath._cli._auth._auth_session.update_env_file"),
        ):
            auth_session = AuthSession("cloud")
            await auth_session.ensure_valid_token()
            mock_refresh.assert_not_called()

    async def test_ensure_valid_token_missing_refresh_token_raises(
        self, mock_auth_config
    ):
        auth_data_no_refresh = {
            "access_token": "old_access_token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "openid profile offline_access",
            "id_token": "old_id_token",
        }

        past_time = time.time() - 3600
        expired_token_claims = {"exp": past_time, "prt_id": "test_prt_id"}

        with (
            patch(
                "uipath._cli._auth._oidc_utils.OidcUtils.get_auth_config",
                new_callable=AsyncMock,
                return_value=mock_auth_config,
            ),
            patch(
                "uipath._cli._auth._auth_session.get_auth_data",
                return_value=TokenData.model_validate(auth_data_no_refresh),
            ),
            patch(
                "uipath._cli._auth._auth_session.get_parsed_token_data",
                return_value=expired_token_claims,
            ),
        ):
            auth_session = AuthSession("cloud")
            with pytest.raises(
                UiPathRuntimeError, match="The refresh token could not be retrieved"
            ):
                await auth_session.ensure_valid_token()
