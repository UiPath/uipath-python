import os
from unittest.mock import AsyncMock, patch

import pytest
from click.testing import CliRunner

from uipath._cli import cli

"""
Unit tests for the 'uipath auth' command.

This test suite covers the following scenarios for the authentication logic:

1.  **UIPATH_URL Environment Variable**:
    Ensures the `auth` command correctly uses the domain from the `UIPATH_URL`
    environment variable when no specific --cloud URL is provided.

2.  **--cloud Flag with Custom URLs**:
    Verifies that the `--cloud` flag correctly accepts custom URLs such as
    staging.uipath.com, alpha.uipath.com, or custom domains.

3.  **Default Behavior**:
    Confirms that the command defaults to https://cloud.uipath.com when no flags
    or environment variables are provided.
"""


class TestAuth:
    @pytest.mark.parametrize(
        "scenario_name, cli_args, env_vars, expected_url_part, expected_select_tenant_return",
        [
            (
                "auth_with_uipath_url_env_variable",
                [],
                {"UIPATH_URL": "https://custom.automationsuite.org/org/tenant"},
                "https://custom.automationsuite.org/identity_/connect/authorize",
                "https://custom.automationsuite.org/DefaultOrg/DefaultTenant",
            ),
            (
                "auth_with_uipath_url_env_variable_with_trailing_slash",
                [],
                {"UIPATH_URL": "https://custom.uipath.com/org/tenant/"},
                "https://custom.uipath.com/identity_/connect/authorize",
                "https://custom.uipath.com/DefaultOrg/DefaultTenant",
            ),
            (
                "auth_with_cloud_alpha_url",
                ["--cloud", "https://alpha.uipath.com", "--force"],
                {"UIPATH_URL": "https://custom.uipath.com/org/tenant"},
                "https://alpha.uipath.com/identity_/connect/authorize",
                "https://alpha.uipath.com/DefaultOrg/DefaultTenant",
            ),
            (
                "auth_with_cloud_staging_url",
                ["--cloud", "https://staging.uipath.com", "--force"],
                {"UIPATH_URL": "https://custom.uipath.com/org/tenant"},
                "https://staging.uipath.com/identity_/connect/authorize",
                "https://staging.uipath.com/DefaultOrg/DefaultTenant",
            ),
            (
                "auth_with_cloud_custom_url",
                ["--cloud", "https://my-custom-domain.com", "--force"],
                {},
                "https://my-custom-domain.com/identity_/connect/authorize",
                "https://my-custom-domain.com/DefaultOrg/DefaultTenant",
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
            "cloud_alpha_url_overrides_env",
            "cloud_staging_url_overrides_env",
            "cloud_custom_url",
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
            patch(
                "uipath._cli._auth._auth_service.PortalService"
            ) as mock_portal_service,
            patch("uipath._cli._auth._auth_service.update_env_file"),
        ):
            mock_server.return_value.start = AsyncMock(
                return_value={"access_token": "test_token"}
            )
            mock_portal_service.return_value.__enter__.return_value.get_tenants_and_organizations.return_value = {
                "tenants": [{"name": "DefaultTenant", "id": "tenant-id"}],
                "organization": {"name": "DefaultOrg", "id": "org-id"},
            }
            mock_portal_service.return_value.__enter__.return_value._select_tenant.return_value = {
                "tenant_id": "tenant-id",
                "organization_id": "org-id",
            }
            mock_portal_service.return_value.__enter__.return_value.resolve_tenant_info.return_value = {
                "tenant_id": "tenant-id",
                "organization_id": "org-id",
            }
            mock_portal_service.return_value.__enter__.return_value.build_tenant_url.return_value = expected_select_tenant_return

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

    def test_auth_with_malformed_cloud_url(self):
        """
        Test that 'uipath auth' handles a malformed --cloud URL gracefully.
        """
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["auth", "--cloud", "custom.uipath.com"])

            assert result.exit_code == 1
            assert "Malformed cloud URL" in result.output
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
            patch(
                "uipath._cli._auth._auth_service.PortalService"
            ) as mock_portal_service,
            patch(
                "uipath._cli._auth._url_utils.resolve_domain",
                return_value="https://alpha.uipath.com",
            ),
            patch("uipath._cli._auth._auth_service.update_env_file"),
        ):
            mock_server.return_value.start = AsyncMock(
                return_value={"access_token": "test_token"}
            )

            portal = mock_portal_service.return_value.__enter__.return_value
            portal.get_tenants_and_organizations.return_value = {
                "tenants": [
                    {"name": "MyTenantName", "id": "tenant-id"},
                    {"name": "OtherTenant", "id": "other-id"},
                ],
                "organization": {"name": "MyOrg", "id": "org-id"},
            }
            portal.resolve_tenant_info.return_value = {
                "tenant_id": "tenant-id",
                "organization_id": "org-id",
            }
            portal.build_tenant_url.return_value = "https://alpha.uipath.com/MyOrg/MyTenantName"
            portal.selected_tenant = "MyTenantName"

            result = runner.invoke(
                cli, ["auth", "--cloud", "https://alpha.uipath.com", "--tenant", "MyTenantName", "--force"]
            )

            assert result.exit_code == 0, result.output
            mock_open.assert_called_once()

            portal.resolve_tenant_info.assert_called_once_with("MyTenantName")
