import os
import time
from typing import Optional

import requests

from ._models import TenantsAndOrganizationInfoResponse, TokenData
from ._oidc_utils import get_auth_config
from ._utils import (
    get_auth_data,
    get_parsed_token_data,
    update_auth_file,
    update_env_file,
)


class PortalService:
    """Service for interacting with the UiPath Portal API"""

    access_token: Optional[str] = None
    prt_id: Optional[str] = None
    domain: Optional[str] = None
    selected_tenant: Optional[str] = None

    _tenants_and_organizations: Optional[TenantsAndOrganizationInfoResponse] = None

    def __init__(
        self,
        domain: str,
        access_token: Optional[str] = None,
        prt_id: Optional[str] = None,
    ):
        self.domain = domain
        self.access_token = access_token
        self.prt_id = prt_id

    def update_token_data(self, token_data: TokenData):
        self.access_token = token_data["access_token"]
        self.prt_id = get_parsed_token_data(token_data).get("prt_id")

    def get_tenants_and_organizations(self) -> TenantsAndOrganizationInfoResponse:
        url = f"https://{self.domain}.uipath.com/{self.prt_id}/portal_/api/filtering/leftnav/tenantsAndOrganizationInfo"
        response = requests.get(
            url, headers={"Authorization": f"Bearer {self.access_token}"}
        )
        if response.ok:
            result = response.json()
            self._tenants_and_organizations = result
            return result
        elif response.status_code == 401:
            raise Exception("Unauthorized")
        else:
            raise Exception(
                f"Failed to get tenants and organizations: {response.status_code} {response.text}"
            )

    def get_uipath_orchestrator_url(self) -> str:
        if self._tenants_and_organizations is None:
            self._tenants_and_organizations = self.get_tenants_and_organizations()
        organization = self._tenants_and_organizations.get("organization")
        if organization is None:
            raise Exception("Organization not found")
        account_name = organization.get("name")
        return f"https://{self.domain}.uipath.com/{account_name}/{self.selected_tenant}/orchestrator_"

    def post_refresh_token_request(self, refresh_token: str) -> TokenData:
        url = f"https://{self.domain}.uipath.com/identity_/connect/token"
        client_id = get_auth_config().get("client_id")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }

        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        response = requests.post(url, data=data, headers=headers)
        if response.ok:
            return response.json()
        elif response.status_code == 401:
            raise Exception("Unauthorized")
        else:
            raise Exception(f"Failed to refresh token: {response.status_code}")

    def ensure_valid_token(self):
        """Ensure the access token is valid and refresh it if necessary.

        This function should be called when running CLI commands to verify authentication.
        It checks if an auth file exists and contains a valid non-expired token.
        If the token is expired, it will attempt to refresh it.
        If no auth file exists, it will raise an exception.

        Raises:
            Exception: If no auth file exists or token refresh fails
        """
        auth_data = get_auth_data()
        claims = get_parsed_token_data(auth_data)
        exp = claims.get("exp")

        if exp is not None and float(exp) > time.time():
            return auth_data.get("access_token")
        refresh_token = auth_data.get("refresh_token")
        if refresh_token is None:
            raise Exception("Refresh token not found")
        token_data = self.post_refresh_token_request(refresh_token)
        update_auth_file(token_data)

        self.access_token = token_data["access_token"]
        self.prt_id = claims.get("prt_id")

        updated_env_contents = {
            "UIPATH_ACCESS_TOKEN": token_data["access_token"],
        }
        update_env_file(updated_env_contents)

    def has_initialized_auth(self):
        try:
            auth_data = get_auth_data()
            if not auth_data or "access_token" not in auth_data:
                return False
            if not os.path.exists(".env"):
                return False
            if not os.getenv("UIPATH_ACCESS_TOKEN"):
                return False

            return True
        except Exception:
            return False
