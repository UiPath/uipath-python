"""Models for interrupt operations in UiPath platform."""

from typing import Any

from pydantic import BaseModel

from ..actions import Action
from ..orchestrator import Job

class InvokeProcess(BaseModel):
    """Model representing a process invocation."""

    name: str
    process_folder_path: str | None = None
    process_folder_key: str | None = None
    input_arguments: dict[str, Any] | None

class WaitJob(BaseModel):
    """Model representing a wait job operation."""

    job: Job
    process_folder_path: str | None = None
    process_folder_key: str | None = None

class CreateTask(BaseModel):
    """Model representing an action creation."""

    title: str
    data: dict[str, Any] | None = None
    assignee: str | None = ""
    app_name: str | None = None
    app_folder_path: str | None = None
    app_folder_key: str | None = None
    app_key: str | None = None
    app_version: int | None = 1

class CreateEscalation(CreateTask):
    """Model representing an escalation creation."""

    pass

class WaitTask(BaseModel):
    """Model representing a wait action operation."""

    action: Action
    app_folder_path: str | None = None
    app_folder_key: str | None = None

class WaitEscalation(WaitTask):
    """Model representing a wait escalation operation."""

    pass
