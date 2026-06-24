"""Service for calling the simulate-component API."""

from typing import Any

from uipath._utils import Endpoint
from uipath.platform.common import BaseService


class SimulateComponentService(BaseService):
    async def simulate(self, payload: dict[str, Any]) -> dict[str, Any]:
        from uipath.platform.common import UiPathConfig

        headers: dict[str, str] = {}
        if UiPathConfig.tenant_id:
            headers["X-UiPath-Internal-TenantId"] = UiPathConfig.tenant_id
        if UiPathConfig.organization_id:
            headers["X-UiPath-Internal-AccountId"] = UiPathConfig.organization_id

        response = await self.request_async(
            "POST",
            url=Endpoint(
                "/agentsruntime_/api/execution/simulations/simulate-component"
            ),
            json=payload,
            headers=headers,
        )
        return response.json()


def _create_simulate_component_service() -> SimulateComponentService:
    from uipath.platform import UiPath

    uipath = UiPath()
    return SimulateComponentService(
        config=uipath._config,
        execution_context=uipath._execution_context,
    )
