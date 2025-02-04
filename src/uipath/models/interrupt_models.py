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
    name: Optional[str] = None
    key: Optional[str] = None
    title: str
    data: Optional[Dict[str, Any]] = None
    app_version: Optional[int] = 1
    assignee: Optional[str] = ""


class WaitAction(BaseModel):
    action: Action
