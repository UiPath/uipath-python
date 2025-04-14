from typing import Any, Dict, Optional

from pydantic import BaseModel

from .actions import Action
from .job import Job


class InvokeProcess(BaseModel):
    name: str
    input_arguments: Optional[Dict[str, Any]]


class WaitJob(BaseModel):
    job: Job


class CreateAction(BaseModel):
    title: str
    data: Optional[Dict[str, Any]] = None
    assignee: Optional[str] = ""
    app_name: Optional[str] = None
    app_folder_path: Optional[str] = None
    app_folder_key: Optional[str] = None
    app_key: Optional[str] = None
    app_version: Optional[int] = 1


class WaitAction(BaseModel):
    action: Action
