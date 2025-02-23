from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Action(BaseModel):
    task_definition_properties_id: Optional[int] = None
    app_tasks_metadata: Optional[Any] = None
    action_label: Optional[str] = None
    status: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    action: Optional[str] = None
    wait_job_state: Optional[str] = None
    organization_unit_fully_qualified_name: Optional[str] = None
    tags: List[Any] = Field(default_factory=list)
    assigned_to_user: Optional[Any] = None
    task_sla_details: List[Any] = Field(default_factory=list)
    completed_by_user: Optional[Any] = None
    task_assignment_criteria: Optional[str] = None
    task_assignees: List[Any] = Field(default_factory=list)
    title: Optional[str] = None
    type: Optional[str] = None
    priority: Optional[str] = None
    assigned_to_user_id: Optional[int] = None
    organization_unit_id: Optional[int] = None
    external_tag: Optional[str] = None
    creator_job_key: Optional[str] = None
    wait_job_key: Optional[str] = None
    last_assigned_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    parent_operation_id: Optional[str] = None
    key: Optional[str] = None
    is_deleted: bool = False
    deleter_user_id: Optional[int] = None
    deletion_time: Optional[datetime] = None
    last_modification_time: Optional[datetime] = None
    last_modifier_user_id: Optional[int] = None
    creation_time: Optional[datetime] = None
    creator_user_id: Optional[int] = None
    id: Optional[int] = None

    class Config:
        populate_by_name = True
        extra = "allow"
        json_encoders = {datetime: lambda v: v.isoformat() if v else None}
        arbitrary_types_allowed = True
