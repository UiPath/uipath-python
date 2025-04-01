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
    name: Optional[str]
    key: Optional[str]
    title: str
    data: Optional[Dict[str, Any]]


class WaitAction(BaseModel):
    action: Action
