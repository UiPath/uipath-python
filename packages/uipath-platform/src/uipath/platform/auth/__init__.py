"""UiPath Auth package.

Provides reusable authentication building blocks: token acquisition,
token management, portal API calls, OIDC configuration, and URL utilities.
"""

from ._auth_service import AuthService
from ._errors import AuthenticationError
from ._models import (
    AccessTokenData,
    AuthConfig,
    AuthorizationRequest,
    OrganizationInfo,
    TenantInfo,
    TenantsAndOrganizationInfoResponse,
)
from ._url_utils import build_service_url, extract_org_tenant, resolve_domain
from ._utils import (
    get_auth_data,
    get_parsed_token_data,
    parse_access_token,
    update_auth_file,
)

__all__ = [
    "AuthService",
    "AuthenticationError",
    "AuthConfig",
    "AuthorizationRequest",
    "AccessTokenData",
    "TenantInfo",
    "OrganizationInfo",
    "TenantsAndOrganizationInfoResponse",
    "build_service_url",
    "extract_org_tenant",
    "resolve_domain",
    "get_auth_data",
    "get_parsed_token_data",
    "parse_access_token",
    "update_auth_file",
]
