"""
Unit tests for OidcUtils.get_auth_config() method.

IMPORTANT: Backwards Compatibility Notice
=========================================
If any values in auth_config.json are changed, we MUST maintain backwards
compatibility with release/2025.10 branches or later.
"""

import json
import os


class TestOidcUtils:
    """Test suite for OidcUtils class."""

    def test_auth_config_backwards_compatibility_v2025_10(self):
        """
        Test that auth_config.json maintains backwards compatibility with release/v2025.10.

        This test validates that the authentication configuration values remain
        unchanged to ensure compatibility with release/v2025.10 and later branches.

        CRITICAL: Any failure indicates a breaking change that requires coordination
        across all supported release branches.
        """
        # Read the actual auth_config.json file
        config_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "src",
            "uipath",
            "_cli",
            "_auth",
            "auth_config.json",
        )

        with open(config_path, "r") as f:
            actual_config = json.load(f)

        # Assert exact values for non-scope fields
        assert actual_config["client_id"] == "36dea5b8-e8bb-423d-8e7b-c808df8f1c00", (
            f"BACKWARDS COMPATIBILITY VIOLATION: client_id has changed! "
            f"Expected: 36dea5b8-e8bb-423d-8e7b-c808df8f1c00, Got: {actual_config['client_id']}"
        )

        assert (
            actual_config["redirect_uri"]
            == "http://localhost:__PY_REPLACE_PORT__/oidc/login"
        ), (
            f"BACKWARDS COMPATIBILITY VIOLATION: redirect_uri has changed! "
            f"Expected: http://localhost:__PY_REPLACE_PORT__/oidc/login, Got: {actual_config['redirect_uri']}"
        )

        assert actual_config["port"] == 8104, (
            f"BACKWARDS COMPATIBILITY VIOLATION: port has changed! "
            f"Expected: 8104, Got: {actual_config['port']}"
        )

        # For scopes, ensure actual scopes are a subset of the allowed scopes (no new scopes allowed)
        allowed_scopes = set(
            [
                "offline_access",
                "ProcessMining",
                "OrchestratorApiUserAccess",
                "StudioWebBackend",
                "IdentityServerApi",
                "ConnectionService",
                "DataService",
                "DocumentUnderstanding",
                "Du.Digitization.Api",
                "Du.Classification.Api",
                "Du.Extraction.Api",
                "Du.Validation.Api",
                "EnterpriseContextService",
                "Directory",
                "JamJamApi",
                "LLMGateway",
                "LLMOps",
                "OMS",
                "RCS.FolderAuthorization",
                "TM.Projects",
                "TM.TestCases",
                "TM.Requirements",
                "TM.TestSets",
            ]
        )

        actual_scopes = set(actual_config["scope"].split())

        assert actual_scopes.issubset(allowed_scopes), (
            f"BACKWARDS COMPATIBILITY VIOLATION: New scopes detected that are not allowed on v2025.10! "
            f"New scopes: {actual_scopes - allowed_scopes}. "
            f"Only subsets of the following scopes are permitted: {sorted(allowed_scopes)}"
        )
