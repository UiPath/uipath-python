"""AutomationOps service for UiPath Platform.

Provides methods for retrieving deployed policies from the AgentHub service.
"""

from typing import Any

from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._models import Endpoint, RequestSpec

_DEPLOYED_POLICY_ENDPOINT = Endpoint("agenthub_/api/policies/deployed-policy")


class AutomationOpsService(BaseService):
    """Service for interacting with UiPath AutomationOps policies via AgentHub."""

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="automation_ops_get_deployed_policy", run_type="uipath")
    def get_deployed_policy(self) -> dict[str, Any]:
        """Retrieve the deployed policy.

        Returns:
            The deployed policy response as a dictionary.
        """
        spec = self._deployed_policy_spec()
        response = self.request(
            spec.method,
            url=spec.endpoint,
            headers=spec.headers,
            scoped="tenant",
        )
        return response.json()

    @traced(name="automation_ops_get_deployed_policy", run_type="uipath")
    async def get_deployed_policy_async(self) -> dict[str, Any]:
        """Retrieve the deployed policy (async).

        Returns:
            The deployed policy response as a dictionary.
        """
        spec = self._deployed_policy_spec()
        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            headers=spec.headers,
            scoped="tenant",
        )
        return response.json()

    def _deployed_policy_spec(self) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=_DEPLOYED_POLICY_ENDPOINT,
        )
