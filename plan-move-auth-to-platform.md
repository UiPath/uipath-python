# Plan: Move Auth from uipath to uipath-platform

## Principles

- **uipath-platform**: reusable auth building blocks (token management, portal API calls, OIDC config, URL utils, models). No CLI dependencies (no click, no ConsoleLogger, no interactive prompts, no browser, no local HTTP server).
- **uipath (CLI)**: `AuthService` (orchestrates the browser-based OAuth flow), `HTTPServer` (local OAuth callback), `cli_auth.py` (click command), interactive tenant selection, `webbrowser.open`, console output.
- **Error handling**: Replace `UiPathRuntimeError` with `AuthenticationError(Exception)` defined in platform. Raise exceptions instead of calling `console.error()` — let the CLI layer catch and display them.

---

## What Goes Where

| uipath-platform (reusable by any lib/agent) | uipath CLI (interactive, local-machine only) |
|---|---|
| `PortalService` (API calls: get tenants, refresh token, ensure_valid_token, enable_studio_web) | `AuthService` (orchestrates browser OAuth + client creds via platform) |
| `OidcUtils`, PKCE helpers, auth config selection | `HTTPServer` + `index.html` + SSL certs (localhost OAuth callback) |
| `_models.py` (AuthConfig, TenantInfo, etc.) | `webbrowser.open` + ConsoleLogger output |
| `_url_utils.py` (resolve_domain, build_service_url, extract_org_tenant) | Interactive tenant selection (prompt user) |
| `_utils.py` (parse_access_token, update_env_file, update_auth_file, get_auth_data) | `cli_auth.py` (click command) |
| `_errors.py` (AuthenticationError) | |
| `ExternalApplicationService` (client credentials — already in platform) | |

**Rationale for HTTPServer staying in CLI**: The browser-based OAuth flow (authorization code + PKCE) requires a human with a browser and a localhost server. An agent or server-side library would use client credentials or pre-configured tokens — never a local HTTP server.

---

## Architecture After Move

```
uipath-platform/src/uipath/platform/auth/
    __init__.py              # public API: PortalService, OidcUtils, AuthenticationError, models
    _errors.py               # AuthenticationError(Exception)
    _models.py               # AuthConfig, AccessTokenData, TenantInfo, OrganizationInfo, TenantsAndOrganizationInfoResponse
    _url_utils.py            # resolve_domain, build_service_url, extract_org_tenant
    _utils.py                # parse_access_token, update_env_file, update_auth_file, get_auth_data, get_parsed_token_data
    _oidc_utils.py           # OidcUtils, PKCE helpers, config file selection
    _portal_service.py       # PortalService (API calls only, no interactive prompts)
    auth_config_cloud.json   # OIDC config for cloud
    auth_config_25_10.json   # OIDC config for AS 25.10

uipath/src/uipath/_cli/
    cli_auth.py              # click command — catches exceptions, displays via ConsoleLogger
    _auth/
        _auth_service.py     # AuthService (orchestrates browser OAuth + client creds)
        _auth_server.py      # HTTPServer (local OAuth callback listener)
        index.html           # OAuth redirect page
        localhost.crt         # SSL cert
        localhost.key         # SSL key
```

---

## PortalService Split

The current `PortalService` mixes API calls with interactive CLI logic. After the move:

**Platform (`PortalService`)** — all API methods, raises exceptions on errors:
- `update_token_data(token_data)`
- `get_tenants_and_organizations()` — raises on error instead of `console.error()`
- `refresh_access_token(refresh_token)` — raises on error
- `ensure_valid_token()` — raises `AuthenticationError` instead of `UiPathRuntimeError`
- `enable_studio_web(base_url)`
- `retrieve_tenant(tenant_name)` — raises if not found (was `_retrieve_tenant`)
- `build_tenant_url()`
- `build_orchestrator_url(base_url)`

**CLI (`cli_auth.py` / `_auth_service.py`)** — handles interactive tenant selection:
- Gets tenant list via `portal_service.get_tenants_and_organizations()`
- Prompts user with `ConsoleLogger.display_options()` / `ConsoleLogger.prompt()`
- Calls `portal_service.retrieve_tenant(selected_name)`

---

## Checklist

### Step 1: Create auth package in uipath-platform
- [X] Create `packages/uipath-platform/src/uipath/platform/auth/` directory
- [X] Create `__init__.py`
- [X] Create `_errors.py` with `AuthenticationError(Exception)`

### Step 2: Move models
- [X] Move `_models.py` (AuthConfig, AccessTokenData, TenantInfo, OrganizationInfo, TenantsAndOrganizationInfoResponse)

### Step 3: Move utility functions
- [X] Move `parse_access_token` and `update_env_file` from `uipath/_utils/_auth.py` into platform `auth/_utils.py`
- [X] Move `update_auth_file`, `get_auth_data`, `get_parsed_token_data` into platform `auth/_utils.py`
- [X] Move `_url_utils.py` (resolve_domain, build_service_url, extract_org_tenant) — remove ConsoleLogger, raise exceptions

### Step 4: Move OIDC utils
- [X] Move `_oidc_utils.py` — remove ConsoleLogger, raise exceptions
- [X] Move static files: `auth_config_cloud.json`, `auth_config_25_10.json`

### Step 5: Move PortalService
- [X] Move `_portal_service.py` to platform
- [X] Remove ConsoleLogger — raise exceptions on errors
- [X] Replace `UiPathRuntimeError` with `AuthenticationError`
- [X] Remove `_select_tenant()` — interactive logic stays in CLI
- [X] Rename `_retrieve_tenant` to `retrieve_tenant` (public)
- [X] Remove `resolve_tenant_info()` — CLI will handle dispatch
- [X] Import `get_httpx_client_kwargs` from `uipath.platform.common` directly

### Step 6: Create `__init__.py` with public API
- [X] Export: `PortalService`, `OidcUtils`, `AuthenticationError`
- [X] Re-export relevant models and utils

### Step 7: Update uipath-platform pyproject.toml
- [X] Check dependencies — `httpx` likely already there, no new deps expected

### Step 8: Update AuthService in CLI
- [X] Update `_auth_service.py` imports to use `uipath.platform.auth` for PortalService, OidcUtils, url_utils, utils, models
- [X] Keep ConsoleLogger, webbrowser.open, HTTPServer in CLI
- [X] Move interactive tenant selection into AuthService or cli_auth.py

### Step 9: Update cli_auth.py
- [X] Update imports
- [X] Catch `AuthenticationError` and display via ConsoleLogger

### Step 10: Clean up uipath package
- [X] Delete moved files from `_cli/_auth/` (keep: `_auth_service.py`, `_auth_server.py`, `index.html`, `localhost.crt`, `localhost.key`)
- [X] Delete `_models.py`, `_url_utils.py`, `_utils.py`, `_oidc_utils.py`, `auth_config_*.json` from `_cli/_auth/`
- [X] Clean up `uipath/_utils/_auth.py` — remove `parse_access_token` and `update_env_file` (moved to platform), keep `resolve_config_from_env` if still used

### Step 11: Move tests to uipath-platform
- [X] Move `test_oidc_utils.py` — update imports to `uipath.platform.auth.*`
- [X] Move `test_portal_service_refresh_token.py` — update imports
- [X] Move `test_portal_service_ensure_valid_token.py` — update imports, replace `UiPathRuntimeError` with `AuthenticationError`
- [X] Keep `test_auth.py` in uipath (tests CLI command) — update imports

### Step 12: Verify
- [X] Run uipath-platform tests
- [X] Run uipath tests
- [X] Run linting/formatting

---

## Open Questions

1. **`_utils/_auth.py` cleanup**: `resolve_config_from_env` already exists in both `uipath/_utils/_auth.py` and `uipath-platform/common/auth.py`. Should we delete the one in uipath entirely? don t worry about it in this PR
2. **`_ssl_context.py`**: `_oidc_utils.py` and `_portal_service.py` currently import `get_httpx_client_kwargs` from `uipath/_utils/_ssl_context.py`, which re-exports from `uipath.platform.common`. After the move, platform modules import directly from `uipath.platform.common._http_config`. No issue expected.

## User directives:

- remove update_env_file from platform. platform should not be concerned of the .env file. that is a cli concern, can we refactor somehow?  def ensure_valid_token(self) -> None: should not also write to file
- why do PortalService is implemented as a context manager? only to close the client? shouldn t we follow the platform approach and make this a proper service that inherits from Base and uses the clients from there? we should be consistent.
