"""Models for interrupt operations in UiPath platform."""

from typing import Any, Dict, Optional

from pydantic import BaseModel

from ..action_center import Task
from ..orchestrator import Job


class InvokeProcess(BaseModel):
    """Model representing a process invocation."""

    name: str
    process_folder_path: Optional[str] = None
    process_folder_key: Optional[str] = None
    input_arguments: Optional[Dict[str, Any]]


class WaitJob(BaseModel):
    """Model representing a wait job operation."""

    job: Job
    process_folder_path: Optional[str] = None
    process_folder_key: Optional[str] = None


class CreateTask(BaseModel):
    """Model representing an action creation."""

    title: str
    data: Optional[Dict[str, Any]] = None
    assignee: Optional[str] = ""
    app_name: Optional[str] = None
    app_folder_path: Optional[str] = None
    app_folder_key: Optional[str] = None
    app_key: Optional[str] = None


class CreateEscalation(CreateTask):
    """Model representing an escalation creation with additional metadata."""

    app_version: Optional[int] = None
    priority: Optional[str] = None
    labels: Optional[list[str]] = None
    is_actionable_message_enabled: Optional[bool] = None
    actionable_message_metadata: Optional[Dict[str, Any]] = None
    agent_id: Optional[str] = None
    instance_id: Optional[str] = None
    job_key: Optional[str] = None
    process_key: Optional[str] = None
    resource_key: Optional[str] = None


class WaitTask(BaseModel):
    """Model representing a wait action operation."""

    action: Task
    app_folder_path: Optional[str] = None
    app_folder_key: Optional[str] = None


class WaitEscalation(WaitTask):
    """Model representing a wait escalation operation."""

    pass
