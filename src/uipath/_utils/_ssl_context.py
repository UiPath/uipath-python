import os
import ssl


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
