"""Orchestrator setup service for UiPath Platform."""

import logging

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext

logger = logging.getLogger(__name__)


class OrchestratorSetupService(BaseService):
    """Service for orchestrator provisioning and licensing operations."""

    def __init__(
        self, config: UiPathApiConfig, execution_context: UiPathExecutionContext
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def enable_first_run(self) -> None:
        """Fire-and-forget POST requests to enable first run for StudioWeb.

        Posts to TryEnableFirstRun and AcquireLicense endpoints.
        """
        paths = [
            "orchestrator_/api/StudioWeb/TryEnableFirstRun",
            "orchestrator_/api/StudioWeb/AcquireLicense",
        ]

        for path in paths:
            try:
                self.request("POST", path)
            except Exception as exc:
                logger.warning(
                    "OrchestratorSetupService enable_first_run: POST %s failed: %s",
                    path,
                    exc,
                )

    async def enable_first_run_async(self) -> None:
        """Fire-and-forget POST requests to enable first run for StudioWeb.

        Posts to TryEnableFirstRun and AcquireLicense endpoints.
        """
        paths = [
            "orchestrator_/api/StudioWeb/TryEnableFirstRun",
            "orchestrator_/api/StudioWeb/AcquireLicense",
        ]

        for path in paths:
            try:
                await self.request_async("POST", path)
            except Exception as exc:
                logger.warning(
                    "OrchestratorSetupService enable_first_run_async: POST %s failed: %s",
                    path,
                    exc,
                )
