from typing import Any, Literal, Optional, TypedDict


class Action(TypedDict):
    status: Literal["Unassigned", "Pending", "Completed"]
    data: Optional[Any]
    action: Optional[str]
    waitJobState: Optional[
        Literal[
            "Pending",
            "Running",
            "Stopping",
            "Terminating",
            "Faulted",
            "Successful",
            "Stopped",
            "Suspended",
            "Resumed",
        ]
    ]
    organizationUnitFullyQualifiedName: Optional[str]
    assignedToUser: Optional[Any]
    title: str
    type: Optional[
        Literal[
            "FormTask",
            "ExternalTask",
            "DocumentValidationTask",
            "DocumentClassificationTask",
            "DataLabelingTask",
            "AppTask",
        ]
    ]
    priority: Optional[Literal["Low", "Medium", "High", "Critical"]]
    assignedToUserId: Optional[int]
    organizationUnitId: Optional[int]
    externalTag: Optional[str]
    creatorJobKey: Optional[str]
    waitJobKey: Optional[str]
    lastAssignedTime: Optional[str]
    completionTime: Optional[str]
    isDeleted: bool
    deleterUserId: Optional[int]
    deletionTime: Optional[str]
    lastModificationTime: Optional[str]
    lastModifierUserId: Optional[int]
    creationTime: Optional[str]
    creatorUserId: Optional[int]
    id: Optional[int]
    key: str
