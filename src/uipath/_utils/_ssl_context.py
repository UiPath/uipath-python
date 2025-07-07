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


def get_httpx_client_kwargs() -> Dict[str, Any]:
    """Get standardized httpx client configuration."""
    client_kwargs: Dict[str, Any] = {"follow_redirects": True, "timeout": 30.0}

    # Check environment variable to disable SSL verification
    disable_ssl_env = os.environ.get("UIPATH_DISABLE_SSL_VERIFY", "").lower()
    disable_ssl_from_env = disable_ssl_env in ("1", "true", "yes", "on")

    if disable_ssl_from_env:
        client_kwargs["verify"] = False
    else:
        # Use system certificates with truststore fallback
        client_kwargs["verify"] = create_ssl_context()

    # Auto-detect proxy from environment variables (httpx handles this automatically)
    # HTTP_PROXY, HTTPS_PROXY, NO_PROXY are read by httpx by default

    return client_kwargs
