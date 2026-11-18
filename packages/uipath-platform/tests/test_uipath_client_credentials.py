from unittest.mock import patch

import pytest

from uipath.platform import UiPath
from uipath.platform.common.auth import TokenData

BASE_URL = "https://cloud.uipath.com/org/tenant"
GET_TOKEN_DATA = "uipath.platform._uipath.ExternalApplicationService.get_token_data"


@pytest.mark.parametrize(
    "client_secret,client_assertion",
    [("app-client-secret", None), (None, "the.oidc.jwt")],
)
def test_client_credentials_exchange_for_token(
    client_secret: str | None, client_assertion: str | None
):
    with patch(
        GET_TOKEN_DATA, return_value=TokenData(access_token="app-token")
    ) as mock_get_token:
        sdk = UiPath(
            base_url=BASE_URL,
            client_id="app-client-id",
            client_secret=client_secret,
            client_assertion=client_assertion,
        )

    mock_get_token.assert_called_once_with(
        "app-client-id", client_secret, None, client_assertion=client_assertion
    )
    assert sdk._config.secret == "app-token"
    assert sdk._config.base_url == BASE_URL


@pytest.mark.parametrize(
    "client_id,client_secret,client_assertion",
    [
        ("app-client-id", None, None),
        (None, "app-client-secret", None),
        (None, None, "the.oidc.jwt"),
        ("app-client-id", "app-client-secret", "the.oidc.jwt"),
    ],
)
def test_incomplete_or_conflicting_credentials_raise(
    client_id: str | None, client_secret: str | None, client_assertion: str | None
):
    with pytest.raises(ValueError):
        UiPath(
            base_url=BASE_URL,
            client_id=client_id,
            client_secret=client_secret,
            client_assertion=client_assertion,
        )
