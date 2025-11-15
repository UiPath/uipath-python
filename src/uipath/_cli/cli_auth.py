from typing import Optional

import click

from ._auth._auth_service import AuthService
from ._utils._common import environment_options
from ._utils._console import ConsoleLogger

console = ConsoleLogger()


@click.command()
@environment_options
@click.option(
    "-f",
    "--force",
    is_flag=True,
    required=False,
    default=False,
    help="Force new token",
)
@click.option(
    "--client-id",
    required=False,
    help="Client ID for client credentials authentication (unattended mode)",
)
@click.option(
    "--client-secret",
    required=False,
    help="Client secret for client credentials authentication (unattended mode)",
)
@click.option(
    "--base-url",
    required=False,
    help="Base URL for the UiPath tenant instance (required for client credentials)",
)
@click.option(
    "--tenant",
    required=False,
    help="Tenant name within UiPath Automation Cloud",
)
@click.option(
    "--scope",
    required=False,
    default="OR.Execution",
    help="Space-separated list of OAuth scopes to request (e.g., 'OR.Execution OR.Queues'). Defaults to 'OR.Execution'",
)
def auth(
    environment: str,
    force: bool = False,
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    base_url: Optional[str] = None,
    tenant: Optional[str] = None,
    scope: Optional[str] = None,
):
    """Authenticate with UiPath Cloud Platform.

    The domain for authentication is determined by the UIPATH_URL environment variable if set.
    Otherwise, it can be specified with --cloud (default), --staging, or --alpha flags.

    Interactive mode (default): Opens browser for OAuth authentication.
    Unattended mode: Use --client-id, --client-secret, --base-url and --scope for client credentials flow.

    Network options:
    - Set HTTP_PROXY/HTTPS_PROXY/NO_PROXY environment variables for proxy configuration
    - Set REQUESTS_CA_BUNDLE to specify a custom CA bundle for SSL verification
    - Set UIPATH_DISABLE_SSL_VERIFY to disable SSL verification (not recommended)
    """
    auth_service = AuthService(
        environment=environment,
        force=force,
        client_id=client_id,
        client_secret=client_secret,
        base_url=base_url,
        tenant=tenant,
        scope=scope,
    )
    with console.spinner("Authenticating with UiPath ..."):
        try:
            auth_service.authenticate()
            console.success(
                "Authentication successful.",
            )
        except KeyboardInterrupt:
            console.error(
                "Authentication cancelled by user.",
            )
