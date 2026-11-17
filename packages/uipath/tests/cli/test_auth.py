import os
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from uipath._cli import cli
from uipath.platform.common import TokenData

"""
Unit tests for the 'uipath auth' command.

This test suite covers the following scenarios for the authentication logic:

1.  **UIPATH_URL Environment Variable**:
    Ensures the `auth` command correctly uses the domain from the `UIPATH_URL`
    environment variable when no specific environment flag is used.

2.  **--alpha Flag**:
    Verifies that the `--alpha` flag correctly uses the 'alpha' environment and
    overrides the `UIPATH_URL` environment variable if it is set.

3.  **--staging Flag**:
    Verifies that the `--staging` flag correctly uses the 'staging' environment and
    overrides the `UIPATH_URL` environment variable if it is set.

4.  **--cloud Flag**:
    Checks that the `--cloud` flag works as expected, using the 'cloud' environment,
    when no `UIPATH_URL` environment variable is set.

5.  **Default Behavior**:
    Confirms that the command defaults to the 'cloud' environment when no flags
    or environment variables are provided.
"""


class TestAuth:
    @pytest.mark.parametrize(
        "scenario_name, cli_args, env_vars, expected_url_part, expected_select_tenant_return",
        [
            (
                "auth_with_uipath_url_env_variable",
                ["--force"],
                {"UIPATH_URL": "https://custom.automationsuite.org/org/tenant"},
                "https://custom.automationsuite.org/identity_/connect/authorize",
                "https://custom.automationsuite.org/DefaultOrg/DefaultTenant",
            ),
            (
                "auth_with_uipath_url_env_variable_with_trailing_slash",
                ["--force"],
                {"UIPATH_URL": "https://custom.uipath.com/org/tenant/"},
                "https://custom.uipath.com/identity_/connect/authorize",
                "https://custom.uipath.com/DefaultOrg/DefaultTenant",
            ),
            (
                "auth_with_alpha_flag",
                ["--alpha", "--force"],
                {"UIPATH_URL": "https://custom.uipath.com/org/tenant"},
                "https://alpha.uipath.com/identity_/connect/authorize",
                "https://alpha.uipath.com/DefaultOrg/DefaultTenant",
            ),
            (
                "auth_with_staging_flag",
                ["--staging", "--force"],
                {"UIPATH_URL": "https://custom.uipath.com/org/tenant"},
                "https://staging.uipath.com/identity_/connect/authorize",
                "https://staging.uipath.com/DefaultOrg/DefaultTenant",
            ),
            (
                "auth_with_cloud_flag",
                ["--cloud", "--force"],
                {},
                "https://cloud.uipath.com/identity_/connect/authorize",
                "https://cloud.uipath.com/DefaultOrg/DefaultTenant",
            ),
            (
                "auth_default_to_cloud",
                ["--force"],
                {},
                "https://cloud.uipath.com/identity_/connect/authorize",
                "https://cloud.uipath.com/DefaultOrg/DefaultTenant",
            ),
        ],
        ids=[
            "uipath_url_env",
            "uipath_url_env_with_trailing_slash",
            "alpha_flag_overrides_env",
            "staging_flag_overrides_env",
            "cloud_flag",
            "default_to_cloud",
        ],
    )
    def test_auth_scenarios(
        self,
        scenario_name,
        cli_args,
        env_vars,
        expected_url_part,
        expected_select_tenant_return,
    ):
        """
        Test 'uipath auth' with different configurations.
        """
        runner = CliRunner()
        with (
            patch("uipath._cli._auth._auth_service.webbrowser.open") as mock_open,
            patch("uipath._cli._auth._auth_service.HTTPServer") as mock_server,
            patch("uipath._cli._auth._auth_service.AuthSession") as mock_auth_session,
            patch("uipath.platform.UiPath") as mock_uipath,
        ):
            mock_uipath.return_value.orchestrator_setup.enable_first_run_async = (
                AsyncMock()
            )
            mock_server.return_value.start = AsyncMock(
                return_value={"access_token": "test_token"}
            )
            session = mock_auth_session.return_value
            session.get_tenants_and_organizations = AsyncMock(
                return_value={
                    "tenants": [{"name": "DefaultTenant", "id": "tenant-id"}],
                    "organization": {"name": "DefaultOrg", "id": "org-id"},
                }
            )
            session._select_tenant = AsyncMock(
                return_value={
                    "tenant_id": "tenant-id",
                    "organization_id": "org-id",
                }
            )
            session.resolve_tenant_info = AsyncMock(
                return_value={
                    "tenant_id": "tenant-id",
                    "organization_id": "org-id",
                }
            )
            session.build_tenant_url = AsyncMock(
                return_value=expected_select_tenant_return,
            )

            with runner.isolated_filesystem():
                for key, value in env_vars.items():
                    os.environ[key] = value

                result = runner.invoke(cli, ["auth"] + cli_args)

                for key in env_vars:
                    del os.environ[key]

                assert result.exit_code == 0, (
                    f"Scenario '{scenario_name}' failed with exit code {result.exit_code}: {result.output}"
                )
                mock_open.assert_called_once()
                call_args = mock_open.call_args[0][0]
                assert expected_url_part in call_args

    def test_auth_with_malformed_url(self):
        """
        Test that 'uipath auth' handles a malformed UIPATH_URL gracefully.
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.environ["UIPATH_URL"] = "custom.uipath.com"
            result = runner.invoke(cli, ["auth"])
            del os.environ["UIPATH_URL"]

            assert result.exit_code == 1
            assert "Malformed UIPATH_URL" in result.output
            assert "custom.uipath.com" in result.output

    def test_auth_with_tenant_flag(self):
        """
        Test that providing --tenant bypasses interactive tenant selection
        and uses the specified tenant name.
        """
        runner = CliRunner()
        with (
            patch("uipath._cli._auth._auth_service.webbrowser.open") as mock_open,
            patch("uipath._cli._auth._auth_service.HTTPServer") as mock_server,
            patch("uipath._cli._auth._auth_service.AuthSession") as mock_auth_session,
            patch(
                "uipath._cli._auth._url_utils.resolve_domain",
                return_value="https://alpha.uipath.com",
            ),
            patch("uipath.platform.UiPath") as mock_uipath,
        ):
            mock_uipath.return_value.orchestrator_setup.enable_first_run_async = (
                AsyncMock()
            )
            mock_server.return_value.start = AsyncMock(
                return_value={"access_token": "test_token"}
            )

            session = mock_auth_session.return_value
            session.get_tenants_and_organizations = AsyncMock(
                return_value={
                    "tenants": [
                        {"name": "MyTenantName", "id": "tenant-id"},
                        {"name": "OtherTenant", "id": "other-id"},
                    ],
                    "organization": {"name": "MyOrg", "id": "org-id"},
                }
            )
            session.resolve_tenant_info = AsyncMock(
                return_value={
                    "tenant_id": "tenant-id",
                    "organization_id": "org-id",
                }
            )
            session.build_tenant_url = AsyncMock(
                return_value="https://alpha.uipath.com/MyOrg/MyTenantName",
            )
            session.selected_tenant = "MyTenantName"
            with runner.isolated_filesystem():
                result = runner.invoke(
                    cli, ["auth", "--alpha", "--tenant", "MyTenantName", "--force"]
                )

                assert result.exit_code == 0, result.output
                mock_open.assert_called_once()

                session.resolve_tenant_info.assert_called_once_with("MyTenantName")

    def test_auth_with_client_assertion(self):
        """
        Test that --client-assertion runs the client credentials flow
        with the OIDC token instead of a client secret.
        """
        runner = CliRunner()
        with (
            patch(
                "uipath._cli._auth._auth_service.ExternalApplicationService"
            ) as mock_service,
            patch("uipath._cli._auth._auth_service.AuthSession") as mock_auth_session,
            patch(
                "uipath._cli._auth._auth_service.get_parsed_token_data",
                return_value={"prt_id": "org-id"},
            ),
        ):
            service = mock_service.return_value
            service._base_url = "https://cloud.uipath.com/MyOrg/MyTenant"
            service.get_token_data_async = AsyncMock(
                return_value=TokenData(access_token="fed-token")
            )
            mock_auth_session.return_value.resolve_tenant_info = AsyncMock(
                return_value={"tenant_id": "tenant-id"}
            )
            with runner.isolated_filesystem():
                result = runner.invoke(
                    cli,
                    [
                        "auth",
                        "--base-url",
                        "https://cloud.uipath.com/MyOrg/MyTenant",
                        "--client-id",
                        "app-client-id",
                        "--client-assertion",
                        "the.oidc.jwt",
                    ],
                )

                assert result.exit_code == 0, result.output
                service.get_token_data_async.assert_awaited_once_with(
                    "app-client-id",
                    None,
                    "OR.Execution",
                    client_assertion="the.oidc.jwt",
                )
                with open(".env") as f:
                    assert "UIPATH_ACCESS_TOKEN=fed-token" in f.read()

    @pytest.mark.parametrize(
        "credential_args",
        [["--client-secret", "secret"], ["--client-assertion", "the.oidc.jwt"]],
    )
    def test_auth_credential_without_client_id_fails(self, credential_args):
        """
        Test that a secret or assertion without --client-id is rejected
        instead of falling back to the interactive browser flow.
        """
        runner = CliRunner()
        with patch("uipath._cli._auth._auth_service.webbrowser.open") as mock_open:
            result = runner.invoke(cli, ["auth", *credential_args])

        assert result.exit_code == 2
        assert "--client-id is required" in result.output
        mock_open.assert_not_called()
