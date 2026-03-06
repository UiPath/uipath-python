from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext


class StudioWebService(BaseService):
    """Service for enabling UiPath Studio Web."""

    def __init__(
        self, config: UiPathApiConfig, execution_context: UiPathExecutionContext
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def enable(self) -> None:
        """Enable Studio Web (TryEnableFirstRun + AcquireLicense)."""
        urls = [
            "/orchestrator_/api/StudioWeb/TryEnableFirstRun",
            "/orchestrator_/api/StudioWeb/AcquireLicense",
        ]
        for url in urls:
            self.request("POST", url)

    async def enable_async(self) -> None:
        """Enable Studio Web (TryEnableFirstRun + AcquireLicense)."""
        urls = [
            "/orchestrator_/api/StudioWeb/TryEnableFirstRun",
            "/orchestrator_/api/StudioWeb/AcquireLicense",
        ]
        for url in urls:
            await self.request_async("POST", url)
