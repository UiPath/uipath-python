"""Service for calling the simulate-component API."""

import json
from typing import Any

from uipath._utils import Endpoint
from uipath.core.serialization import serialize_json
from uipath.platform.common import BaseService
from uipath.platform.constants import (
    HEADER_INTERNAL_ACCOUNT_ID,
    HEADER_INTERNAL_TENANT_ID,
)
from uipath.platform.errors import EnrichedException

_SIMULATE_COMPONENT = Endpoint(
    "/agentsruntime_/api/unifiedEvals/simulations/simulate-component"
)
_LEGACY_SIMULATE_COMPONENT = Endpoint(
    "/agentsruntime_/api/execution/simulations/simulate-component"
)


class SimulateComponentService(BaseService):
    async def simulate(self, payload: dict[str, Any]) -> dict[str, Any]:
        from uipath.platform.common import UiPathConfig

        headers: dict[str, str] = {}
        if UiPathConfig.tenant_id:
            headers[HEADER_INTERNAL_TENANT_ID] = UiPathConfig.tenant_id
        if UiPathConfig.organization_id:
            headers[HEADER_INTERNAL_ACCOUNT_ID] = UiPathConfig.organization_id

        body = json.loads(serialize_json(payload))
        try:
            response = await self.request_async(
                "POST", url=_SIMULATE_COMPONENT, json=body, headers=headers
            )
        except EnrichedException as error:
            if error.status_code not in (404, 405):
                raise
            response = await self.request_async(
                "POST", url=_LEGACY_SIMULATE_COMPONENT, json=body, headers=headers
            )
        return response.json()


def _create_simulate_component_service() -> SimulateComponentService:
    from uipath.platform import UiPath

    uipath = UiPath()
    return SimulateComponentService(
        config=uipath._config,
        execution_context=uipath._execution_context,
    )
