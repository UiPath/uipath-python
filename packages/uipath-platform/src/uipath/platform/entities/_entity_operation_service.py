"""Operation invokes for the Data Fabric entities surface.

Runs the operations an entity declares. Entity schema, records and ontology
files are handled by their own services; all of them are exposed through
`EntitiesService`.
"""

from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

from httpx import HTTPStatusError
from pydantic import ValidationError
from tenacity import stop_after_attempt

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import header_folder
from ..common._models import Endpoint, RequestSpec
from ..errors._enriched_exception import EnrichedException
from ._entity_resolution import RoutingStrategy
from ._entity_schema_service import folder_key_or_none
from .entities import EntityOperationResult, QueryRoutingOverrideContext

# BaseService retries 5xx, 408 and 429. An operation can write, so it is sent once.
_request_once = BaseService.request.retry_with(stop=stop_after_attempt(1))  # type: ignore[attr-defined]
_request_once_async = BaseService.request_async.retry_with(  # type: ignore[attr-defined]
    stop=stop_after_attempt(1)
)

# CEP gives an invoke up to 120s, and a Code operation runs as a job inside that
# budget. The client default (30s) would give up on a write that later succeeds.
_INVOKE_TIMEOUT = 150.0


class EntityOperationService(BaseService):
    """HTTP service for invoking the operations an entity declares.

    Backend target: ``datafabric_/api/v3/entities/{entity}/operations``.

    !!! warning "Preview Feature"
        This service is currently experimental. Behavior and parameters are
        subject to change in future versions.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        routing_strategy: Optional[RoutingStrategy] = None,
    ) -> None:
        """Initialise the operation service."""
        super().__init__(config=config, execution_context=execution_context)
        self._routing_strategy = routing_strategy

    def invoke(
        self,
        entity_name: str,
        operation_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        folder_key: Optional[str] = None,
    ) -> EntityOperationResult:
        """Internal implementation; see `EntitiesService.invoke_operation()`."""
        if folder_key is None and self._routing_strategy is not None:
            entity_name, folder_key = self._route(
                entity_name, self._routing_strategy.resolve()
            )
        spec = self._invoke_operation_spec(
            entity_name, operation_name, arguments, folder_key
        )
        try:
            response = _request_once(
                self,
                spec.method,
                spec.endpoint,
                headers=spec.headers,
                json=spec.json,
                timeout=_INVOKE_TIMEOUT,
            )
        except EnrichedException as exc:
            refused = self._refused_result(exc)
            if refused is None:
                raise
            return refused
        return EntityOperationResult.model_validate(response.json())

    async def invoke_async(
        self,
        entity_name: str,
        operation_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        folder_key: Optional[str] = None,
    ) -> EntityOperationResult:
        """Async variant of `invoke()`."""
        if folder_key is None and self._routing_strategy is not None:
            entity_name, folder_key = self._route(
                entity_name, await self._routing_strategy.resolve_async()
            )
        spec = self._invoke_operation_spec(
            entity_name, operation_name, arguments, folder_key
        )
        try:
            response = await _request_once_async(
                self,
                spec.method,
                spec.endpoint,
                headers=spec.headers,
                json=spec.json,
                timeout=_INVOKE_TIMEOUT,
            )
        except EnrichedException as exc:
            refused = self._refused_result(exc)
            if refused is None:
                raise
            return refused
        return EntityOperationResult.model_validate(response.json())

    @staticmethod
    def _route(
        entity_name: str, routing: Optional[QueryRoutingOverrideContext]
    ) -> Tuple[str, Optional[str]]:
        """Return the entity's routed name and folder, or its name and no folder.

        Matches the configured name or the overwrite's name, since callers often
        hold the fetched entity, which carries the overwrite's. Data Fabric names
        are case-insensitive, so the match is too.
        """
        wanted = entity_name.casefold()
        for entry in routing.entity_routings if routing else []:
            names = (entry.entity_name, entry.override_entity_name)
            if wanted in (name.casefold() for name in names if name):
                return entry.override_entity_name or entity_name, entry.folder_id
        return entity_name, None

    @staticmethod
    def _refused_result(exc: EnrichedException) -> Optional[EntityOperationResult]:
        """Parse a 400 whose JSON body carries an ``outcome``; None for any other error."""
        cause = exc.__cause__
        if exc.status_code != 400 or not isinstance(cause, HTTPStatusError):
            return None
        try:
            body = cause.response.json()
        except ValueError:
            return None
        if not isinstance(body, dict) or "outcome" not in body:
            return None
        try:
            return EntityOperationResult.model_validate(body)
        except ValidationError:
            return None

    @staticmethod
    def _invoke_operation_spec(
        entity_name: str,
        operation_name: str,
        arguments: Optional[Dict[str, Any]],
        folder_key: Optional[str],
    ) -> RequestSpec:
        """Build the POST spec for invoking an operation."""
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"datafabric_/api/v3/entities/{quote(entity_name, safe='')}"
                f"/operations/{quote(operation_name, safe='')}"
            ),
            headers=header_folder(folder_key_or_none(folder_key), None),
            json=arguments or {},
        )
