from unittest.mock import patch

import httpx
import pytest

from uipath.platform.common._external_application_service import (
    ExternalApplicationService,
)
from uipath.platform.common.auth import TokenData
from uipath.platform.errors import EnrichedException

IDENTITY_SERVICE_PATH = "uipath.platform.common._external_application_service.IdentityService.get_client_credentials_token"


class TestExternalApplicationService:
    @pytest.mark.parametrize(
        "url,expected_domain",
        [
            ("https://alpha.uipath.com", "alpha"),
            ("https://sub.alpha.uipath.com", "alpha"),
            ("https://staging.uipath.com", "staging"),
            ("https://env.staging.uipath.com", "staging"),
            ("https://cloud.uipath.com", "cloud"),
            ("https://org.cloud.uipath.com", "cloud"),
            ("https://something-else.com", "cloud"),
            ("not-a-url", "cloud"),
        ],
    )
    def test_extract_domain_from_base_url(self, url: str, expected_domain: str):
        service = ExternalApplicationService(url)
        assert service._domain == expected_domain

    def test_get_access_token_success(self):
        service = ExternalApplicationService("https://cloud.uipath.com")
        fake_token = TokenData(access_token="fake-token")

        with patch(IDENTITY_SERVICE_PATH, return_value=fake_token):
            token = service.get_token_data("client-id", "client-secret")

        assert token.access_token == "fake-token"

    def test_get_access_token_invalid_client(self):
        service = ExternalApplicationService("https://cloud.uipath.com")
        response = httpx.Response(
            400, json={}, request=httpx.Request("POST", "http://test")
        )

        with patch(
            IDENTITY_SERVICE_PATH,
            side_effect=httpx.HTTPStatusError(
                "", request=response.request, response=response
            ),
        ):
            with pytest.raises(EnrichedException) as exc:
                service.get_token_data("bad-id", "bad-secret")

        assert "400" in str(exc.value)

    def test_get_access_token_unauthorized(self):
        service = ExternalApplicationService("https://cloud.uipath.com")
        response = httpx.Response(
            401, json={}, request=httpx.Request("POST", "http://test")
        )

        with patch(
            IDENTITY_SERVICE_PATH,
            side_effect=httpx.HTTPStatusError(
                "", request=response.request, response=response
            ),
        ):
            with pytest.raises(EnrichedException) as exc:
                service.get_token_data("bad-id", "bad-secret")

        assert "401" in str(exc.value)

    def test_get_access_token_unexpected_status(self):
        service = ExternalApplicationService("https://cloud.uipath.com")
        response = httpx.Response(
            500, json={}, request=httpx.Request("POST", "http://test")
        )

        with patch(
            IDENTITY_SERVICE_PATH,
            side_effect=httpx.HTTPStatusError(
                "", request=response.request, response=response
            ),
        ):
            with pytest.raises(EnrichedException) as exc:
                service.get_token_data("client-id", "client-secret")

        assert "500" in str(exc.value)

    def test_get_access_token_network_error(self):
        service = ExternalApplicationService("https://cloud.uipath.com")

        with patch(
            IDENTITY_SERVICE_PATH, side_effect=httpx.RequestError("network down")
        ):
            with pytest.raises(Exception) as exc:
                service.get_token_data("client-id", "client-secret")

        assert "Network error during authentication" in str(exc.value)

    def test_get_access_token_unexpected_exception(self):
        service = ExternalApplicationService("https://cloud.uipath.com")

        with patch(IDENTITY_SERVICE_PATH, side_effect=ValueError("weird error")):
            with pytest.raises(Exception) as exc:
                service.get_token_data("client-id", "client-secret")

        assert "Unexpected error during authentication" in str(exc.value)


class TestExternalApplicationServiceDelegation:
    def test_delegates_to_identity_service(self):
        service = ExternalApplicationService("https://cloud.uipath.com")
        fake_token = TokenData(access_token="delegated-token")

        with patch(
            "uipath.platform.common._external_application_service.IdentityService.get_client_credentials_token",
            return_value=fake_token,
        ) as mock_get_token:
            result = service.get_token_data("my-id", "my-secret", scope="OR.Execution")

        mock_get_token.assert_called_once_with(
            domain="https://cloud.uipath.com",
            client_id="my-id",
            client_secret="my-secret",
            scope="OR.Execution",
        )
        assert result.access_token == "delegated-token"

    @pytest.mark.parametrize(
        "base_url,expected_domain",
        [
            ("https://alpha.uipath.com", "https://alpha.uipath.com"),
            ("https://sub.alpha.uipath.com", "https://alpha.uipath.com"),
            ("https://staging.uipath.com", "https://staging.uipath.com"),
            ("https://env.staging.uipath.com", "https://staging.uipath.com"),
            ("https://cloud.uipath.com", "https://cloud.uipath.com"),
            ("https://org.cloud.uipath.com", "https://cloud.uipath.com"),
            ("https://something-else.com", "https://cloud.uipath.com"),
        ],
    )
    def test_domain_mapping_for_delegation(self, base_url: str, expected_domain: str):
        service = ExternalApplicationService(base_url)
        fake_token = TokenData(access_token="token")

        with patch(
            "uipath.platform.common._external_application_service.IdentityService.get_client_credentials_token",
            return_value=fake_token,
        ) as mock_get_token:
            service.get_token_data("id", "secret")

        called_domain = mock_get_token.call_args.kwargs["domain"]
        assert called_domain == expected_domain
