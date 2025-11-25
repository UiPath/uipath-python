"""Data model for an Action in the UiPath platform."""

from datetime import datetime
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field, field_serializer

class Action(BaseModel):
    """Model representing an Action in the UiPath platform."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    @field_serializer("*", when_used="json")
    def serialize_datetime(self, value):
        """Serialize datetime fields to ISO 8601 format for JSON output."""
        if isinstance(value, datetime):
            return value.isoformat() if value else None
        return value

    task_definition_properties_id: int | None = Field(
        default=None, alias="taskDefinitionPropertiesId"
    )
    app_tasks_metadata: Any | None = Field(default=None, alias="appTasksMetadata")
    action_label: str | None = Field(default=None, alias="actionLabel")
    status: Union[str, int] | None = None
    data: dict[str, Any] | None = None
    action: str | None = None
    wait_job_state: str | None = Field(default=None, alias="waitJobState")
    organization_unit_fully_qualified_name: str | None = Field(
        default=None, alias="organizationUnitFullyQualifiedName"
    )
    tags: list[Any] | None = None
    assigned_to_user: Any | None = Field(default=None, alias="assignedToUser")
    task_sla_details: list[Any] | None = Field(default=None, alias="taskSlaDetails")
    completed_by_user: Any | None = Field(default=None, alias="completedByUser")
    task_assignment_criteria: str | None = Field(
        default=None, alias="taskAssignmentCriteria"
    )
    task_assignees: list[Any] | None = Field(default=None, alias="taskAssignees")
    title: str | None = None
    type: str | None = None
    priority: str | None = None
    assigned_to_user_id: int | None = Field(default=None, alias="assignedToUserId")
    organization_unit_id: int | None = Field(
        default=None, alias="organizationUnitId"
    )
    external_tag: str | None = Field(default=None, alias="externalTag")
    creator_job_key: str | None = Field(default=None, alias="creatorJobKey")
    wait_job_key: str | None = Field(default=None, alias="waitJobKey")
    last_assigned_time: datetime | None = Field(
        default=None, alias="lastAssignedTime"
    )
    completion_time: datetime | None = Field(default=None, alias="completionTime")
    parent_operation_id: str | None = Field(default=None, alias="parentOperationId")
    key: str | None = None
    is_deleted: bool = Field(default=False, alias="isDeleted")
    deleter_user_id: int | None = Field(default=None, alias="deleterUserId")
    deletion_time: datetime | None = Field(default=None, alias="deletionTime")
    last_modification_time: datetime | None = Field(
        default=None, alias="lastModificationTime"
    )
    last_modifier_user_id: int | None = Field(
        default=None, alias="lastModifierUserId"
    )
    creation_time: datetime | None = Field(default=None, alias="creationTime")
    creator_user_id: int | None = Field(default=None, alias="creatorUserId")
    id: int | None = None
