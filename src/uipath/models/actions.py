from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_serializer


class Action(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    @field_serializer("*", when_used="json")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            return value.isoformat() if value else None
        return value

    task_definition_properties_id: Optional[int] = Field(
        default=None, alias="taskDefinitionPropertiesId"
    )
    app_tasks_metadata: Optional[Any] = Field(default=None, alias="appTasksMetadata")
    action_label: Optional[str] = Field(default=None, alias="actionLabel")
    status: Optional[Union[str, int]] = None
    data: Optional[Dict[str, Any]] = None
    action: Optional[str] = None
    wait_job_state: Optional[str] = Field(default=None, alias="waitJobState")
    organization_unit_fully_qualified_name: Optional[str] = Field(
        default=None, alias="organizationUnitFullyQualifiedName"
    )
    tags: Optional[List[Any]] = None
    assigned_to_user: Optional[Any] = Field(default=None, alias="assignedToUser")
    task_sla_details: Optional[List[Any]] = Field(default=None, alias="taskSlaDetails")
    completed_by_user: Optional[Any] = Field(default=None, alias="completedByUser")
    task_assignment_criteria: Optional[str] = Field(
        default=None, alias="taskAssignmentCriteria"
    )
    task_assignees: Optional[List[Any]] = Field(default=None, alias="taskAssignees")
    title: Optional[str] = None
    type: Optional[str] = None
    priority: Optional[str] = None
    assigned_to_user_id: Optional[int] = Field(default=None, alias="assignedToUserId")
    organization_unit_id: Optional[int] = Field(
        default=None, alias="organizationUnitId"
    )
    external_tag: Optional[str] = Field(default=None, alias="externalTag")
    creator_job_key: Optional[str] = Field(default=None, alias="creatorJobKey")
    wait_job_key: Optional[str] = Field(default=None, alias="waitJobKey")
    last_assigned_time: Optional[datetime] = Field(
        default=None, alias="lastAssignedTime"
    )
    completion_time: Optional[datetime] = Field(default=None, alias="completionTime")
    parent_operation_id: Optional[str] = Field(default=None, alias="parentOperationId")
    key: Optional[str] = None
    is_deleted: bool = Field(default=False, alias="isDeleted")
    deleter_user_id: Optional[int] = Field(default=None, alias="deleterUserId")
    deletion_time: Optional[datetime] = Field(default=None, alias="deletionTime")
    last_modification_time: Optional[datetime] = Field(
        default=None, alias="lastModificationTime"
    )
    last_modifier_user_id: Optional[int] = Field(
        default=None, alias="lastModifierUserId"
    )
    creation_time: Optional[datetime] = Field(default=None, alias="creationTime")
    creator_user_id: Optional[int] = Field(default=None, alias="creatorUserId")
    id: Optional[int] = None
