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
    folder_path: str | None = Field(default=None, alias="folderPath")
    folder_key: str | None = Field(default=None, alias="folderKey")
    payload: Any | None = Field(default=None, alias="interruptObject", exclude=True)

    model_config = ConfigDict(validate_by_name=True)
