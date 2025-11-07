"""Service command groups for UiPath CLI.

All services are explicitly imported to ensure:
- File renames break loudly (import error) not silently
- Clear dependency graph
- Fast startup (no auto-discovery overhead)
- Debuggable registration
"""

from .cli_buckets import buckets

__all__ = ["buckets", "register_service_commands"]


def register_service_commands(cli_group):
    """Register all service command groups with the root CLI.

    This function maintains explicitness while reducing registration boilerplate.
    Benefits:
    - File renames break loudly (import error) not silently
    - Clear list of all registered services
    - Easy to comment out services during development

    Args:
        cli_group: The root Click group to register services with

    Returns:
        The cli_group for method chaining

    Industry Precedent:
        AWS CLI, Azure CLI, and gcloud all use explicit registration.
    """
    services = [buckets]

    for service in services:
        cli_group.add_command(service)

    return cli_group
