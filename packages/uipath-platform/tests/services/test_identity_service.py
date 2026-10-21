import httpx
import pytest
from pytest_httpx import HTTPXMock

from uipath.platform.identity import IdentityService


class TestIdentityServiceRefreshAccessToken:
    @pytest.mark.parametrize("use_async", [False, True])
    async def test_refresh_success(self, httpx_mock: HTTPXMock, use_async: bool):
        domain = "https://cloud.uipath.com"
        httpx_mock.add_response(
            url=f"{domain}/identity_/connect/token",
            method="POST",
            status_code=200,
            json={
                "access_token": "new-access-token",
                "refresh_token": "new-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
        )

        service = IdentityService(domain)
        if use_async:
            token = await service.refresh_access_token_async(
                refresh_token="old-refresh-token",
                client_id="my-client-id",
            )
        else:
            token = service.refresh_access_token(
                refresh_token="old-refresh-token",
                client_id="my-client-id",
            )

        assert token.access_token == "new-access-token"
        assert token.refresh_token == "new-refresh-token"
        assert token.expires_in == 3600
        assert token.token_type == "Bearer"

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_refresh_401_raises(self, httpx_mock: HTTPXMock, use_async: bool):
        domain = "https://cloud.uipath.com"
        httpx_mock.add_response(
            url=f"{domain}/identity_/connect/token",
            method="POST",
            status_code=401,
            json={"error": "invalid_grant"},
        )

        service = IdentityService(domain)
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            if use_async:
                await service.refresh_access_token_async(
                    refresh_token="expired-token",
                    client_id="my-client-id",
                )
            else:
                service.refresh_access_token(
                    refresh_token="expired-token",
                    client_id="my-client-id",
                )

        assert exc_info.value.response.status_code == 401


class TestIdentityServiceGetClientCredentialsToken:
    @pytest.mark.parametrize("use_async", [False, True])
    async def test_client_credentials_success(
        self, httpx_mock: HTTPXMock, use_async: bool
    ):
        domain = "https://cloud.uipath.com"
        httpx_mock.add_response(
            url=f"{domain}/identity_/connect/token",
            method="POST",
            status_code=200,
            json={
                "access_token": "cc-access-token",
                "expires_in": 7200,
                "token_type": "Bearer",
                "scope": "OR.Execution",
            },
        )

        service = IdentityService(domain)
        if use_async:
            token = await service.get_client_credentials_token_async(
                client_id="app-client-id",
                client_secret="app-client-secret",
                scope="OR.Execution",
            )
        else:
            token = service.get_client_credentials_token(
                client_id="app-client-id",
                client_secret="app-client-secret",
                scope="OR.Execution",
            )

        assert token.access_token == "cc-access-token"
        assert token.scope == "OR.Execution"

    @pytest.mark.parametrize("use_async", [False, True])
    async def test_client_assertion_replaces_secret(
        self, httpx_mock: HTTPXMock, use_async: bool
    ):
        domain = "https://cloud.uipath.com"
        httpx_mock.add_response(
            url=f"{domain}/identity_/connect/token",
            method="POST",
            status_code=200,
            json={"access_token": "fed-access-token", "token_type": "Bearer"},
        )

        service = IdentityService(domain)
        if use_async:
            token = await service.get_client_credentials_token_async(
                client_id="app-client-id", client_assertion="the.oidc.jwt"
            )
        else:
            token = service.get_client_credentials_token(
                client_id="app-client-id", client_assertion="the.oidc.jwt"
            )

        assert token.access_token == "fed-access-token"
        request = httpx_mock.get_request()
        assert request is not None
        form = dict(httpx.QueryParams(request.content.decode()))
        assert form == {
            "grant_type": "client_credentials",
            "client_id": "app-client-id",
            "scope": "OR.Execution",
            "client_assertion": "the.oidc.jwt",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
        }

    @pytest.mark.parametrize(
        "secret,assertion", [(None, None), ("app-client-secret", "the.oidc.jwt")]
    )
    def test_requires_exactly_one_credential(
        self, secret: str | None, assertion: str | None
    ):
        service = IdentityService("https://cloud.uipath.com")
        with pytest.raises(ValueError):
            service.get_client_credentials_token(
                client_id="app-client-id",
                client_secret=secret,
                client_assertion=assertion,
            )
