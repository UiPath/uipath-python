import os
import ssl
from typing import Any, Dict


def expand_path(path):
    """Expand environment variables and user home directory in path."""
    if not path:
        return path
    # Expand environment variables like $HOME
    path = os.path.expandvars(path)
    # Expand user home directory ~
    path = os.path.expanduser(path)
    return path


def get_ca_bundle_path() -> str | None:
    """Resolve CA bundle path from environment variables.

    Returns None if SSL verification is disabled via UIPATH_DISABLE_SSL_VERIFY.
    Otherwise returns the CA bundle path with priority:
    SSL_CERT_FILE > REQUESTS_CA_BUNDLE > certifi default.
    """
    disable_ssl_env = os.environ.get("UIPATH_DISABLE_SSL_VERIFY", "").lower()
    if disable_ssl_env in ("1", "true", "yes", "on"):
        return None

    import certifi

    ssl_cert_file = expand_path(os.environ.get("SSL_CERT_FILE"))
    requests_ca_bundle = expand_path(os.environ.get("REQUESTS_CA_BUNDLE"))

    return ssl_cert_file or requests_ca_bundle or certifi.where()


def create_ssl_context(cafile: str):
    """Create an SSL context for httpx clients.

    Args:
        cafile: Path to the CA bundle file.
    """
    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        ssl_cert_dir = expand_path(os.environ.get("SSL_CERT_DIR"))

        return ssl.create_default_context(
            cafile=cafile,
            capath=ssl_cert_dir,
        )


def get_httpx_client_kwargs(
    headers: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """Get standardized httpx client configuration.

    Args:
        headers: Optional headers to merge with platform headers (e.g. licensing).
            Caller headers take priority on key conflicts.
    """
    client_kwargs: Dict[str, Any] = {"follow_redirects": True, "timeout": 30.0}

    ca_bundle = get_ca_bundle_path()
    client_kwargs["verify"] = create_ssl_context(ca_bundle) if ca_bundle else False

    from ._config import UiPathConfig
    from .constants import HEADER_LICENSING_CONTEXT

    merged_headers: Dict[str, str] = {}
    licensing_context = UiPathConfig.licensing_context
    if licensing_context:
        merged_headers[HEADER_LICENSING_CONTEXT] = licensing_context
    if headers:
        merged_headers.update(headers)
    if merged_headers:
        client_kwargs["headers"] = merged_headers

    return client_kwargs
