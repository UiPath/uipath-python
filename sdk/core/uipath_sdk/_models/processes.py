from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class Process(BaseModel):
    Key: str
    ProcessKey: str
    ProcessVersion: str
    IsLatestVersion: bool
    IsProcessDeleted: bool
    Description: str
    Name: str
    EnvironmentVariables: Optional[str]
    ProcessType: str
    RequiresUserInteraction: bool
    IsAttended: bool
    IsCompiled: bool
    FeedId: str
    JobPriority: str
    SpecificPriorityValue: int
    TargetFramework: str
    Id: int
    RetentionAction: str
    RetentionPeriod: int
    StaleRetentionAction: str
    StaleRetentionPeriod: int
    Arguments: Optional[Dict[str, Optional[Any]]]
    Tags: List[str]
    Environment: Optional[str] = None
    CurrentVersion: Optional[Dict[str, Any]] = None
    EntryPoint: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True
        extra = "allow"
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}
        arbitrary_types_allowed = True
