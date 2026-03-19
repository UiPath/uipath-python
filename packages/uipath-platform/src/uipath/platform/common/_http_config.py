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


def create_ssl_context():
    # Try truststore first (system certificates)
    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        # Fallback to manual certificate configuration
        import certifi

        ssl_cert_file = expand_path(os.environ.get("SSL_CERT_FILE"))
        requests_ca_bundle = expand_path(os.environ.get("REQUESTS_CA_BUNDLE"))
        ssl_cert_dir = expand_path(os.environ.get("SSL_CERT_DIR"))

        return ssl.create_default_context(
            cafile=ssl_cert_file or requests_ca_bundle or certifi.where(),
            capath=ssl_cert_dir,
        )


def is_ssl_verification_disabled() -> bool:
    """Check if SSL verification is disabled via UIPATH_DISABLE_SSL_VERIFY."""
    return os.environ.get("UIPATH_DISABLE_SSL_VERIFY", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
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

    if is_ssl_verification_disabled():
        client_kwargs["verify"] = False
    else:
        client_kwargs["verify"] = create_ssl_context()

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
