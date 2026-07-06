"""Platform-backed implementation of the core governance provider protocols.

Thin adapter around :class:`GovernanceService` that exposes only the
methods required by
:class:`uipath.core.governance.GovernancePolicyProvider` and
:class:`uipath.core.governance.GovernanceCompensationProvider`.

Wrap an existing :class:`GovernanceService` (e.g.
``UiPathPlatformGovernanceProvider(service=UiPath().governance)``) or
pass ``config``/``execution_context`` to construct one inline.
"""

from __future__ import annotations

from typing import Any

from uipath.core.governance import GovernRequest, PolicyContext, PolicyResponse

from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ._governance_service import GovernanceService


class UiPathPlatformGovernanceProvider:
    """Platform-backed governance provider.

    Implements both
    :class:`uipath.core.governance.GovernancePolicyProvider` and
    :class:`uipath.core.governance.GovernanceCompensationProvider` by
    delegating to :class:`GovernanceService`.

    Args:
        service: Existing :class:`GovernanceService` to delegate to.
            Useful for tests and for sharing an SDK service across
            consumers. When omitted, a fresh service is built from the
            ``config`` and ``execution_context`` kwargs.
        config: Required when ``service`` is not supplied.
        execution_context: Required when ``service`` is not supplied.
    """

    def __init__(
        self,
        service: GovernanceService | None = None,
        *,
        config: UiPathApiConfig | None = None,
        execution_context: UiPathExecutionContext | None = None,
    ) -> None:
        if service is None:
            if config is None or execution_context is None:
                raise ValueError(
                    "UiPathPlatformGovernanceProvider requires either a "
                    "GovernanceService instance or both config and "
                    "execution_context."
                )
            service = GovernanceService(
                config=config, execution_context=execution_context
            )
        self._service = service

    @property
    def service(self) -> GovernanceService:
        """The underlying :class:`GovernanceService` instance."""
        return self._service

    # ── GovernancePolicyProvider ─────────────────────────────────────

    def get_policy(self, context: PolicyContext) -> PolicyResponse:
        """Fetch the policy pack — delegates to ``GovernanceService``."""
        return self._service.get_policy(context)

    async def get_policy_async(self, context: PolicyContext) -> PolicyResponse:
        """Async variant of :meth:`get_policy`."""
        return await self._service.get_policy_async(context)

    # ── GovernanceCompensationProvider ───────────────────────────────

    def compensate(self, request: GovernRequest) -> None:
        """Fire the compensating ``/runtime/govern`` POST."""
        self._service._compensate(request)

    async def compensate_async(self, request: GovernRequest) -> None:
        """Async variant of :meth:`compensate`."""
        await self._service._compensate_async(request)

    # ── Custom telemetry events ──────────────────────────────────────

    def track_event(
        self,
        *,
        event_name: str,
        data: dict[str, Any] | None = None,
        operation_id: str | None = None,
    ) -> None:
        """Record a custom telemetry event — delegates to ``GovernanceService``.

        See :meth:`GovernanceService._track_event` for parameter
        semantics — in particular, the ``operation_id`` → trace-id
        fallback.
        """
        self._service._track_event(
            event_name=event_name, data=data, operation_id=operation_id
        )

    async def track_event_async(
        self,
        *,
        event_name: str,
        data: dict[str, Any] | None = None,
        operation_id: str | None = None,
    ) -> None:
        """Async variant of :meth:`track_event`."""
        await self._service._track_event_async(
            event_name=event_name, data=data, operation_id=operation_id
        )
