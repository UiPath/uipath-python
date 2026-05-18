"""Module defining resume trigger types and data models."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UiPathResumeTriggerType(str, Enum):
    """Constants representing different types of resume job triggers in the system."""

    NONE = "None"
    QUEUE_ITEM = "QueueItem"
    JOB = "Job"
    TASK = "Task"
    TIMER = "Timer"
    INBOX = "Inbox"
    API = "Api"
    DEEP_RAG = "DeepRag"
    BATCH_RAG = "BatchRag"
    INDEX_INGESTION = "IndexIngestion"
    IXP_EXTRACTION = "IxpExtraction"
    IXP_VS_ESCALATION = "IxpVsEscalation"


class UiPathResumeTriggerName(str, Enum):
    """Constants representing specific names for resume job triggers in the system."""

    UNKNOWN = "Unknown"
    QUEUE_ITEM = "QueueItem"
    JOB = "Job"
    TASK = "Task"
    ESCALATION = "Escalation"
    TIMER = "Timer"
    INBOX = "Inbox"
    API = "Api"
    DEEP_RAG = "DeepRag"
    BATCH_RAG = "BatchRag"
    INDEX_INGESTION = "IndexIngestion"
    EXTRACTION = "Extraction"
    IXP_VS_ESCALATION = "IxpVsEscalation"
    JOB_RAW = "JobRaw"
    INDEX_INGESTION_RAW = "IndexIngestionRaw"
    DEEP_RAG_RAW = "DeepRagRaw"


class UiPathApiTrigger(BaseModel):
    """API resume trigger request."""

    inbox_id: str | None = Field(default=None, alias="inboxId")
    request: Any = None

    model_config = ConfigDict(validate_by_name=True)


class UiPathIntegrationTrigger(BaseModel):
    """Integration Services (Inbox) resume trigger request.

    Mirrors Orchestrator's `IntegrationResumeDto`: the configuration needed to
    register a remote event trigger through the Connections service and
    correlate the eventual payload back to the suspended job via `inbox_id`.
    """

    connector: str = Field(alias="connector")
    connection_id: str = Field(alias="connectionId")
    operation: str = Field(alias="operation")
    object_name: str = Field(alias="objectName")
    filter_expression: str | None = Field(default=None, alias="filterExpression")
    parameters: dict[str, str] | None = Field(default=None, alias="parameters")
    inbox_id: str = Field(alias="inboxId")

    model_config = ConfigDict(validate_by_name=True)


class UiPathResumeTrigger(BaseModel):
    """Information needed to resume execution."""

    interrupt_id: str | None = Field(default=None, alias="interruptId")
    trigger_type: UiPathResumeTriggerType = Field(
        default=UiPathResumeTriggerType.API, alias="triggerType"
    )
    trigger_name: UiPathResumeTriggerName = Field(
        default=UiPathResumeTriggerName.UNKNOWN, alias="triggerName", exclude=True
    )
    item_key: str | None = Field(default=None, alias="itemKey")
    api_resume: UiPathApiTrigger | None = Field(default=None, alias="apiResume")
    integration_resume: UiPathIntegrationTrigger | None = Field(
        default=None, alias="integrationResume"
    )
    folder_path: str | None = Field(default=None, alias="folderPath")
    folder_key: str | None = Field(default=None, alias="folderKey")
    payload: Any | None = Field(default=None, alias="interruptObject", exclude=True)

    model_config = ConfigDict(validate_by_name=True)
