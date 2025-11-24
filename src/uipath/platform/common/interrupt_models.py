"""Models for interrupt operations in UiPath platform."""

from typing import Any, Dict, Optional

from pydantic import BaseModel

from ..actions import Action
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


class CreateAction(BaseModel):
    """Model representing an action creation."""

    title: str
    data: Optional[Dict[str, Any]] = None
    assignee: Optional[str] = ""
    app_name: Optional[str] = None
    app_folder_path: Optional[str] = None
    app_folder_key: Optional[str] = None
    app_key: Optional[str] = None
    app_version: Optional[int] = 1


class WaitAction(BaseModel):
    """Model representing a wait action operation."""

    action: Action
    app_folder_path: Optional[str] = None
    app_folder_key: Optional[str] = None
