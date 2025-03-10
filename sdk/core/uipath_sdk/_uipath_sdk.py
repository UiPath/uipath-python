from os import environ as env
from typing import Optional

from dotenv import load_dotenv

from ._config import Config
from ._execution_context import ExecutionContext
from ._services import (
    ActionsService,
    ApiClient,
    AssetsService,
    BucketsService,
    ConnectionsService,
    ContextGroundingService,
    ProcessesService,
    QueuesService,
)
from ._utils import setup_logging
from ._utils.constants import (
    ENV_BASE_URL,
    ENV_UIPATH_ACCESS_TOKEN,
    ENV_UNATTENDED_USER_ACCESS_TOKEN,
)

load_dotenv()


class UiPathSDK:
    """
    The main UiPath SDK class that provides access to various UiPath Automation Cloud services.
    """

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        secret: Optional[str] = None,
        debug: bool = False,
    ) -> None:
        """
        Initialize the UiPath SDK.

        Args:
            base_url (Optional[str]): The base URL for the UiPath Automation Cloud instance.
                If not provided, it will be read from the `UIPATH_URL` environment variable.
            secret (Optional[str]): The authentication token for accessing UiPath services.
                If not provided, it will try to read from `UNATTENDED_USER_ACCESS_TOKEN`
                or `UIPATH_ACCESS_TOKEN` environment variables.
            debug (bool): Enable debug logging if set to True. Defaults to False.
        """
        base_url_value = base_url or env.get(ENV_BASE_URL)
        secret_value = (
            secret
            or env.get(ENV_UNATTENDED_USER_ACCESS_TOKEN)
            or env.get(ENV_UIPATH_ACCESS_TOKEN)
        )

        self._config = Config(
            # We use type: ignore here because base_url and secret can be None at this point,
            # but Config validates and raises ValueError if they're None.
            # This validation happens at runtime, but the type checker doesn't know this.
            base_url=base_url_value,  # type: ignore
            secret=secret_value,  # type: ignore
        )

        setup_logging(debug)
        self._execution_context = ExecutionContext()

    @property
    def api_client(self) -> ApiClient:
        """
        Low-level client for making direct HTTP requests to the UiPath API.
        """
        return ApiClient(self._config, self._execution_context)

    @property
    def assets(self) -> AssetsService:
        """
        Assets are key-value pairs that can be used to store configuration data,
        credentials, and other settings used by automation processes.
        """
        return AssetsService(self._config, self._execution_context)

    @property
    def processes(self) -> ProcessesService:
        """
        Processes (also known as automations or workflows) are the core units of
        automation in UiPath, representing sequences of activities that perform
        specific business tasks.
        """
        return ProcessesService(self._config, self._execution_context)

    @property
    def actions(self) -> ActionsService:
        """
        Actions are task-based automation components that can be integrated into
        applications and processes. They represent discrete units of work that can
        be triggered and monitored through the UiPath API.
        """
        return ActionsService(self._config, self._execution_context)

    @property
    def buckets(self) -> BucketsService:
        """
        Get the Buckets service for managing storage buckets.

        Buckets provide a way to store and manage files and other data used
        by your automation processes.

        Returns:
            BucketsService: Service for managing storage buckets.
        """
        return BucketsService(self._config, self._execution_context)

    @property
    def connections(self) -> ConnectionsService:
        """
        Get the Connections service for managing external service connections.

        This service allows you to manage connections to external systems and
        services that your automation processes interact with.

        Returns:
            ConnectionsService: Service for managing external connections.
        """
        return ConnectionsService(self._config, self._execution_context)

    @property
    def context_grounding(self) -> ContextGroundingService:
        """
        Get the Context Grounding service for managing semantic automation contexts.

        This service helps in managing and understanding the context in which
        automation processes operate, particularly useful for AI-enabled automation.

        Returns:
            ContextGroundingService: Service for managing semantic automation contexts.
        """
        return ContextGroundingService(self._config, self._execution_context)

    @property
    def queues(self) -> QueuesService:
        """
        Get the Queues service for managing UiPath queues.

        Queues are used to manage and distribute work items across your automation
        processes, enabling scalable and distributed processing.

        Returns:
            QueuesService: Service for managing UiPath queues.
        """
        return QueuesService(self._config, self._execution_context)
