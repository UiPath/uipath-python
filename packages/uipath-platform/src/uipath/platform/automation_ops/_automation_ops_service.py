"""AutomationOps service for UiPath Platform.

Provides methods for retrieving deployed policies from the RoboticsOps service.
"""

from typing import Any

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._models import Endpoint, RequestSpec


_DEPLOYED_POLICY_ENDPOINT = Endpoint("/roboticsops_/api/policy/deployed-policy")


class AutomationOpsService(BaseService):
    """Service for interacting with UiPath AutomationOps (RoboticsOps) policies."""

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def get_deployed_policy(self) -> dict[str, Any]:
        """Retrieve the deployed policy.

        Returns:
            The deployed policy response as a dictionary.
        """
        spec = RequestSpec(
            method="GET",
            endpoint=_DEPLOYED_POLICY_ENDPOINT,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            headers=spec.headers,
            scoped="org",
        )
        return response.json()

    async def get_deployed_policy_async(self) -> dict[str, Any]:
        """Retrieve the deployed policy (async).

        Returns:
            The deployed policy response as a dictionary.
        """
        spec = RequestSpec(
            method="GET",
            endpoint=_DEPLOYED_POLICY_ENDPOINT,
        )
        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            headers=spec.headers,
            scoped="org",
        )
        return response.json()
