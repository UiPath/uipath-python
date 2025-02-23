from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Action(BaseModel):
    taskDefinitionPropertiesId: Optional[int] = None
    appTasksMetadata: Optional[Any] = None
    actionLabel: Optional[str] = None
    status: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    action: Optional[str] = None
    waitJobState: Optional[str] = None
    organizationUnitFullyQualifiedName: Optional[str] = None
    tags: List[Any] = Field(default_factory=list)
    assignedToUser: Optional[Any] = None
    taskSlaDetails: List[Any] = Field(default_factory=list)
    completedByUser: Optional[Any] = None
    taskAssignmentCriteria: Optional[str] = None
    taskAssignees: List[Any] = Field(default_factory=list)
    title: Optional[str] = None
    type: Optional[str] = None
    priority: Optional[str] = None
    assignedToUserId: Optional[int] = None
    organizationUnitId: Optional[int] = None
    externalTag: Optional[str] = None
    creatorJobKey: Optional[str] = None
    waitJobKey: Optional[str] = None
    lastAssignedTime: Optional[datetime] = None
    completionTime: Optional[datetime] = None
    parentOperationId: Optional[str] = None
    key: Optional[str] = None
    isDeleted: bool = False
    deleterUserId: Optional[int] = None
    deletionTime: Optional[datetime] = None
    lastModificationTime: Optional[datetime] = None
    lastModifierUserId: Optional[int] = None
    creationTime: Optional[datetime] = None
    creatorUserId: Optional[int] = None
    id: Optional[int] = None

    class Config:
        populate_by_name = True
        extra = "allow"
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}
        arbitrary_types_allowed = True
