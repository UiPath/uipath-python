"""Service command groups for UiPath CLI.

All services are explicitly imported to ensure:
- File renames break loudly (import error) not silently
- Clear dependency graph
- Fast startup (no auto-discovery overhead)
- Debuggable registration
"""

# Explicit imports (Phase 1 - Tracer bullet)
from .cli_buckets import buckets

# Phase 3 - High priority (uncomment as implemented)
# from .cli_assets import assets
# from .cli_queues import queues
# from .cli_jobs import jobs
# from .cli_processes import processes

# Phase 4 - Lower priority (uncomment as implemented)
# from .cli_folders import folders
# from .cli_connections import connections
# from .cli_entities import entities
# from .cli_documents import documents
# from .cli_attachments import attachments

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
    services = [
        buckets,  # Phase 1
        # assets,   # Phase 3
        # queues,   # Phase 3
        # jobs,     # Phase 3
        # processes,# Phase 3
        # folders,  # Phase 4
        # connections, # Phase 4
        # entities, # Phase 4
        # documents, # Phase 4
        # attachments, # Phase 4
    ]

    for service in services:
        cli_group.add_command(service)

    return cli_group
