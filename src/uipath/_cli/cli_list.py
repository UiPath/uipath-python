import json
from typing import List, Protocol, Any, Dict, Callable

import click

from ._utils._common import environment_options, get_env_vars
from ._utils._console import ConsoleLogger
from ..telemetry import track

from .._config import Config
from .._execution_context import ExecutionContext
from .._services import EntitiesService, AssetsService

console = ConsoleLogger()


class CLIListable(Protocol):
    """Protocol for services that support listing"""
    def _list(self, **kwargs) -> List[Any]:
        ...

def create_service(resource_type: str) -> CLIListable:
    """Service factory - creates the appropriate service"""
    [base_url, token] = get_env_vars()

    config = Config(base_url=base_url, secret=token)
    execution_context = ExecutionContext()

    services: Dict[str, Callable[[], CLIListable]] = {
        'entities': lambda: EntitiesService(config, execution_context),
        'assets': lambda: AssetsService(config, execution_context),
    }

    if resource_type not in services:
        available = ', '.join(services.keys())
        raise ValueError(f"Unknown resource type '{resource_type}'. Available: {available}")

    return services[resource_type]()

@click.command()
@click.argument('resource_type')
@click.option('--folder-path', '-f', help='Folder path to list resources from')
def get(
    resource_type: str,
    folder_path: str = None):
    """List resources of a given type."""

    with console.spinner(f"Fetching {resource_type}..."):
        try:
            service: CLIListable = create_service(resource_type)
            # Only pass folder_path if it's provided
            kwargs = {}
            if folder_path:
                kwargs['folder_path'] = folder_path
            list_results = service._list(**kwargs)

            data = [item.model_dump(mode='json') for item in list_results]
            console.success(json.dumps(data, indent=2))

        except Exception as e:
            console.error(f"Error fetching {resource_type}: {e}")
            raise click.Abort()

