"""Automation Tracker (BTS) models for UiPath Platform.

Models for tracking business transactions and operations
via the Business Transaction Service, used for Process Mining.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class TransactionStatus(str, Enum):
    """Status of a BTS transaction."""

    UNKNOWN = "Unknown"
    SUCCESSFUL = "Successful"
    FAILED = "Failed"


class OperationStatus(str, Enum):
    """Status of a BTS operation."""

    UNKNOWN = "Unknown"
    SUCCESSFUL = "Successful"
    FAILED = "Failed"
    CANCELLED = "Cancelled"
    ABANDONED = "Abandoned"


class TransactionPayload(BaseModel):
    """Wire-format payload for BTS transaction start/end endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    organization_id: str = Field(alias="organizationId")
    tenant_id: str = Field(alias="tenantId")
    transaction_id: str = Field(alias="transactionId")
    name: str
    reference: str
    timestamp: datetime
    fingerprint: str
    result: Optional[str] = None
    status: str
    attributes: Dict[str, str] = Field(default_factory=dict)


class OperationPayload(BaseModel):
    """Wire-format payload for BTS operation start/end endpoints."""

    model_config = ConfigDict(populate_by_name=True)

    organization_id: str = Field(alias="organizationId")
    tenant_id: str = Field(alias="tenantId")
    transaction_id: str = Field(alias="transactionId")
    operation_id: str = Field(alias="operationId")
    parent_operation: Optional[str] = Field(default=None, alias="parentOperation")
    name: str
    timestamp: datetime
    status: str
    attributes: Dict[str, str] = Field(default_factory=dict)
    result: Optional[str] = None
    fingerprint: str


class BusinessObjectPayload(BaseModel):
    """Wire-format payload for BTS business object tracking."""

    model_config = ConfigDict(populate_by_name=True)

    organization_id: str = Field(alias="organizationId")
    tenant_id: str = Field(alias="tenantId")
    operation_id: str = Field(alias="operationId")
    timestamp: datetime
    fingerprint: str
    type: str
    key: str
    interaction_type: str = Field(alias="interactionType")
