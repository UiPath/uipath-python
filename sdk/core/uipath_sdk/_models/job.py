from typing import Any, Dict, Optional

from pydantic import BaseModel


class Job(BaseModel):
    Key: Optional[str] = None
    StartTime: Optional[str] = None
    EndTime: Optional[str] = None
    State: Optional[str] = None
    JobPriority: Optional[str] = None
    SpecificPriorityValue: Optional[int] = None
    Robot: Optional[Dict[str, Any]] = None
    Release: Optional[Dict[str, Any]] = None
    ResourceOverwrites: Optional[str] = None
    Source: Optional[str] = None
    SourceType: Optional[str] = None
    BatchExecutionKey: Optional[str] = None
    Info: Optional[str] = None
    CreationTime: Optional[str] = None
    CreatorUserId: Optional[int] = None
    LastModificationTime: Optional[str] = None
    LastModifierUserId: Optional[int] = None
    DeletionTime: Optional[str] = None
    DeleterUserId: Optional[int] = None
    IsDeleted: Optional[bool] = None
    InputArguments: Optional[str] = None
    OutputArguments: Optional[str] = None
    HostMachineName: Optional[str] = None
    HasErrors: Optional[bool] = None
    HasWarnings: Optional[bool] = None
    Id: int
