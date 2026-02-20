"""Automation Tracker (BTS) service for UiPath Platform.

Provides HTTP client methods for tracking business transactions
and operations via the Business Transaction Service, used for Process Mining.
All errors are logged but never raised, ensuring BTS failures
cannot break agent execution.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..._utils import Endpoint, RequestSpec
from ..._utils.constants import ENV_ORGANIZATION_ID, ENV_TENANT_ID
from ...tracing import traced
from ..common import BaseService, UiPathApiConfig, UiPathExecutionContext
from .automation_tracker import (
    OperationPayload,
    OperationStatus,
    TransactionPayload,
    TransactionStatus,
)


class AutomationTrackerService(BaseService):
    """Service for tracking business transactions and operations via BTS.

    This service provides methods to start/end transactions and operations
    for Process Mining tracking. All errors are logged but never raised,
    ensuring BTS failures cannot break agent execution.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self._organization_id = os.getenv(ENV_ORGANIZATION_ID, "")
        self._tenant_id = os.getenv(ENV_TENANT_ID, "")

    def _send(self, endpoint: str, payload_dict: Dict[str, Any]) -> None:
        """Send a POST request to BTS, logging but never raising errors."""
        spec = RequestSpec(
            method="POST",
            endpoint=Endpoint(f"/automationtracker_/{endpoint}"),
            json=payload_dict,
        )
        try:
            self.request(
                spec.method,
                url=spec.endpoint,
                json=spec.json,
            )
        except Exception:
            self._logger.error(
                "Failed to send request to BTS endpoint %s",
                endpoint,
                exc_info=True,
            )

    async def _send_async(self, endpoint: str, payload_dict: Dict[str, Any]) -> None:
        """Send an async POST request to BTS, logging but never raising errors."""
        spec = RequestSpec(
            method="POST",
            endpoint=Endpoint(f"/automationtracker_/{endpoint}"),
            json=payload_dict,
        )
        try:
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                json=spec.json,
            )
        except Exception:
            self._logger.error(
                "Failed to send request to BTS endpoint %s",
                endpoint,
                exc_info=True,
            )

    # ── Transaction methods ──────────────────────────────────────────

    @traced(name="automation_tracker_start_transaction", run_type="uipath")
    def start_transaction(
        self,
        *,
        transaction_id: str,
        name: str,
        reference: str,
        fingerprint: str,
        status: TransactionStatus = TransactionStatus.UNKNOWN,
        result: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Start tracking a business transaction."""
        payload = TransactionPayload(
            organization_id=self._organization_id,
            tenant_id=self._tenant_id,
            transaction_id=transaction_id,
            name=name,
            reference=reference,
            timestamp=timestamp or datetime.now(timezone.utc),
            fingerprint=fingerprint,
            result=result,
            status=status.value,
            attributes=attributes or {},
        )
        self._send(
            "track/transaction/start", payload.model_dump(by_alias=True, mode="json")
        )

    @traced(name="automation_tracker_start_transaction", run_type="uipath")
    async def start_transaction_async(
        self,
        *,
        transaction_id: str,
        name: str,
        reference: str,
        fingerprint: str,
        status: TransactionStatus = TransactionStatus.UNKNOWN,
        result: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Start tracking a business transaction (async)."""
        payload = TransactionPayload(
            organization_id=self._organization_id,
            tenant_id=self._tenant_id,
            transaction_id=transaction_id,
            name=name,
            reference=reference,
            timestamp=timestamp or datetime.now(timezone.utc),
            fingerprint=fingerprint,
            result=result,
            status=status.value,
            attributes=attributes or {},
        )
        await self._send_async(
            "track/transaction/start", payload.model_dump(by_alias=True, mode="json")
        )

    @traced(name="automation_tracker_end_transaction", run_type="uipath")
    def end_transaction(
        self,
        *,
        transaction_id: str,
        name: str,
        reference: str,
        fingerprint: str,
        status: TransactionStatus = TransactionStatus.UNKNOWN,
        result: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """End tracking a business transaction."""
        payload = TransactionPayload(
            organization_id=self._organization_id,
            tenant_id=self._tenant_id,
            transaction_id=transaction_id,
            name=name,
            reference=reference,
            timestamp=timestamp or datetime.now(timezone.utc),
            fingerprint=fingerprint,
            result=result,
            status=status.value,
            attributes=attributes or {},
        )
        self._send(
            "track/transaction/end", payload.model_dump(by_alias=True, mode="json")
        )

    @traced(name="automation_tracker_end_transaction", run_type="uipath")
    async def end_transaction_async(
        self,
        *,
        transaction_id: str,
        name: str,
        reference: str,
        fingerprint: str,
        status: TransactionStatus = TransactionStatus.UNKNOWN,
        result: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """End tracking a business transaction (async)."""
        payload = TransactionPayload(
            organization_id=self._organization_id,
            tenant_id=self._tenant_id,
            transaction_id=transaction_id,
            name=name,
            reference=reference,
            timestamp=timestamp or datetime.now(timezone.utc),
            fingerprint=fingerprint,
            result=result,
            status=status.value,
            attributes=attributes or {},
        )
        await self._send_async(
            "track/transaction/end", payload.model_dump(by_alias=True, mode="json")
        )

    # ── Operation methods ────────────────────────────────────────────

    @traced(name="automation_tracker_start_operation", run_type="uipath")
    def start_operation(
        self,
        *,
        transaction_id: str,
        operation_id: str,
        name: str,
        fingerprint: str,
        parent_operation: Optional[str] = None,
        status: OperationStatus = OperationStatus.UNKNOWN,
        result: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Start tracking an operation within a transaction."""
        payload = OperationPayload(
            organization_id=self._organization_id,
            tenant_id=self._tenant_id,
            transaction_id=transaction_id,
            operation_id=operation_id,
            parent_operation=parent_operation,
            name=name,
            timestamp=timestamp or datetime.now(timezone.utc),
            status=status.value,
            attributes=attributes or {},
            result=result,
            fingerprint=fingerprint,
        )
        self._send(
            "track/operation/start", payload.model_dump(by_alias=True, mode="json")
        )

    @traced(name="automation_tracker_start_operation", run_type="uipath")
    async def start_operation_async(
        self,
        *,
        transaction_id: str,
        operation_id: str,
        name: str,
        fingerprint: str,
        parent_operation: Optional[str] = None,
        status: OperationStatus = OperationStatus.UNKNOWN,
        result: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Start tracking an operation within a transaction (async)."""
        payload = OperationPayload(
            organization_id=self._organization_id,
            tenant_id=self._tenant_id,
            transaction_id=transaction_id,
            operation_id=operation_id,
            parent_operation=parent_operation,
            name=name,
            timestamp=timestamp or datetime.now(timezone.utc),
            status=status.value,
            attributes=attributes or {},
            result=result,
            fingerprint=fingerprint,
        )
        await self._send_async(
            "track/operation/start", payload.model_dump(by_alias=True, mode="json")
        )

    @traced(name="automation_tracker_end_operation", run_type="uipath")
    def end_operation(
        self,
        *,
        transaction_id: str,
        operation_id: str,
        name: str,
        fingerprint: str,
        parent_operation: Optional[str] = None,
        status: OperationStatus = OperationStatus.UNKNOWN,
        result: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """End tracking an operation within a transaction."""
        payload = OperationPayload(
            organization_id=self._organization_id,
            tenant_id=self._tenant_id,
            transaction_id=transaction_id,
            operation_id=operation_id,
            parent_operation=parent_operation,
            name=name,
            timestamp=timestamp or datetime.now(timezone.utc),
            status=status.value,
            attributes=attributes or {},
            result=result,
            fingerprint=fingerprint,
        )
        self._send(
            "track/operation/end", payload.model_dump(by_alias=True, mode="json")
        )

    @traced(name="automation_tracker_end_operation", run_type="uipath")
    async def end_operation_async(
        self,
        *,
        transaction_id: str,
        operation_id: str,
        name: str,
        fingerprint: str,
        parent_operation: Optional[str] = None,
        status: OperationStatus = OperationStatus.UNKNOWN,
        result: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """End tracking an operation within a transaction (async)."""
        payload = OperationPayload(
            organization_id=self._organization_id,
            tenant_id=self._tenant_id,
            transaction_id=transaction_id,
            operation_id=operation_id,
            parent_operation=parent_operation,
            name=name,
            timestamp=timestamp or datetime.now(timezone.utc),
            status=status.value,
            attributes=attributes or {},
            result=result,
            fingerprint=fingerprint,
        )
        await self._send_async(
            "track/operation/end", payload.model_dump(by_alias=True, mode="json")
        )
