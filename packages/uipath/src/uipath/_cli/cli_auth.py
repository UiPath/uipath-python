import asyncio

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
    client_id: str | None = None,
    client_secret: str | None = None,
    base_url: str | None = None,
    tenant: str | None = None,
    scope: str | None = None,
):
    r"""Authenticate with UiPath Cloud Platform.

    The authentication domain is determined in the following order:

    1. The ``UIPATH_URL`` environment variable (if set).
    2. A flag: ``--cloud`` (default), ``--staging``, or ``--alpha``.

    **Modes:**

    - Interactive (default): Opens a browser window for OAuth authentication.
    - Unattended: Uses the client credentials flow. Requires ``--client-id``,
      ``--client-secret``, ``--base-url``, and ``--scope``.

    **Environment Variables:**

    - ``HTTP_PROXY`` / ``HTTPS_PROXY`` / ``NO_PROXY`` — proxy configuration.
    - ``REQUESTS_CA_BUNDLE`` — path to a custom CA bundle for SSL verification.
    - ``UIPATH_DISABLE_SSL_VERIFY`` — disables SSL verification (not recommended).

    **Examples:**

        Interactive login (opens browser for OAuth):

        $ uipath auth

        Unattended login using client credentials:

        $ uipath auth --base-url https://cloud.uipath.com/organization/tenant --client-id 00000000-0000-0000-0000-000000000000 --client-secret 'secret_value_here'

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
            asyncio.run(auth_service.authenticate())
            console.success(
                "Authentication successful.",
            )
        except KeyboardInterrupt:
            console.error(
                "Authentication cancelled by user.",
            )
