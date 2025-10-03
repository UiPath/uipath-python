import httpx
import pytest
from pytest_httpx import HTTPXMock

from uipath._services.external_application_service import ExternalApplicationService
from uipath.models.exceptions import EnrichedException


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

    @pytest.mark.parametrize(
        "domain,expected_url",
        [
            ("alpha", "https://alpha.uipath.com/identity_/connect/token"),
            ("staging", "https://staging.uipath.com/identity_/connect/token"),
            ("cloud", "https://cloud.uipath.com/identity_/connect/token"),
            ("unknown", "https://cloud.uipath.com/identity_/connect/token"),
        ],
    )
    def test_get_token_url(self, domain: str, expected_url: str):
        service = ExternalApplicationService("https://cloud.uipath.com")
        service._domain = domain
        assert service.get_token_url() == expected_url

    def test_get_access_token_success(self, httpx_mock: HTTPXMock):
        service = ExternalApplicationService("https://cloud.uipath.com")

        token_url = service.get_token_url()
        httpx_mock.add_response(
            url=token_url,
            method="POST",
            status_code=200,
            json={"access_token": "fake-token"},
        )

        token = service.get_token_data("client-id", "client-secret")
        assert token.access_token == "fake-token"

    def test_get_access_token_invalid_client(self, httpx_mock: HTTPXMock):
        service = ExternalApplicationService("https://cloud.uipath.com")

        token_url = service.get_token_url()
        httpx_mock.add_response(url=token_url, method="POST", status_code=400, json={})

        with pytest.raises(EnrichedException) as exc:
            service.get_token_data("bad-id", "bad-secret")

        assert "400" in str(exc.value)

    def test_get_access_token_unauthorized(self, httpx_mock: HTTPXMock):
        service = ExternalApplicationService("https://cloud.uipath.com")

        token_url = service.get_token_url()
        httpx_mock.add_response(url=token_url, method="POST", status_code=401, json={})

        with pytest.raises(EnrichedException) as exc:
            service.get_token_data("bad-id", "bad-secret")

        assert "401" in str(exc.value)

    def test_get_access_token_unexpected_status(self, httpx_mock: HTTPXMock):
        service = ExternalApplicationService("https://cloud.uipath.com")

        token_url = service.get_token_url()
        httpx_mock.add_response(url=token_url, method="POST", status_code=500, json={})

        with pytest.raises(EnrichedException) as exc:
            service.get_token_data("client-id", "client-secret")

        assert "500" in str(exc.value).lower()

    def test_get_access_token_network_error(self, monkeypatch):
        service = ExternalApplicationService("https://cloud.uipath.com")

        def fake_client_post(*args, **kwargs):
            raise httpx.RequestError("network down")

        monkeypatch.setattr(httpx.Client, "post", fake_client_post)

        with pytest.raises(Exception) as exc:
            service.get_token_data("client-id", "client-secret")

        assert "Network error during authentication" in str(exc.value)

    def test_get_access_token_unexpected_exception(self, monkeypatch):
        service = ExternalApplicationService("https://cloud.uipath.com")

        def fake_client_post(*args, **kwargs):
            raise ValueError("weird error")

        monkeypatch.setattr(httpx.Client, "post", fake_client_post)

        with pytest.raises(Exception) as exc:
            service.get_token_data("client-id", "client-secret")

        assert "Unexpected error during authentication" in str(exc.value)
