"""Models for Orchestrator Jobs."""

from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class JobState(str, Enum):
    """Job state enum."""

    SUCCESSFUL = "successful"
    FAULTED = "faulted"
    SUSPENDED = "suspended"
    RUNNING = "running"
    PENDING = "pending"


class JobErrorInfo(BaseModel):
    """Model representing job error information."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    code: Optional[str] = Field(default=None, alias="Code")
    title: Optional[str] = Field(default=None, alias="Title")
    detail: Optional[str] = Field(default=None, alias="Detail")
    category: Optional[str] = Field(default=None, alias="Category")
    status: Optional[int] = Field(default=None, alias="Status")


class Job(BaseModel):
    """Model representing an orchestrator job."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    key: Optional[str] = Field(default=None, alias="Key")
    start_time: Optional[str] = Field(default=None, alias="StartTime")
    end_time: Optional[str] = Field(default=None, alias="EndTime")
    # 2.3.0 change to JobState enum
    state: Optional[str] = Field(default=None, alias="State")
    job_priority: Optional[str] = Field(default=None, alias="JobPriority")
    specific_priority_value: Optional[int] = Field(
        default=None, alias="SpecificPriorityValue"
    )
    robot: Optional[Dict[str, Any]] = Field(default=None, alias="Robot")
    release: Optional[Dict[str, Any]] = Field(default=None, alias="Release")
    resource_overwrites: Optional[str] = Field(default=None, alias="ResourceOverwrites")
    source: Optional[str] = Field(default=None, alias="Source")
    source_type: Optional[str] = Field(default=None, alias="SourceType")
    batch_execution_key: Optional[str] = Field(default=None, alias="BatchExecutionKey")
    info: Optional[str] = Field(default=None, alias="Info")
    creation_time: Optional[str] = Field(default=None, alias="CreationTime")
    creator_user_id: Optional[int] = Field(default=None, alias="CreatorUserId")
    last_modification_time: Optional[str] = Field(
        default=None, alias="LastModificationTime"
    )
    last_modifier_user_id: Optional[int] = Field(
        default=None, alias="LastModifierUserId"
    )
    deletion_time: Optional[str] = Field(default=None, alias="DeletionTime")
    deleter_user_id: Optional[int] = Field(default=None, alias="DeleterUserId")
    is_deleted: Optional[bool] = Field(default=None, alias="IsDeleted")
    input_arguments: Optional[str] = Field(default=None, alias="InputArguments")
    input_file: Optional[str] = Field(default=None, alias="InputFile")
    output_arguments: Optional[str] = Field(default=None, alias="OutputArguments")
    output_file: Optional[str] = Field(default=None, alias="OutputFile")
    host_machine_name: Optional[str] = Field(default=None, alias="HostMachineName")
    has_errors: Optional[bool] = Field(default=None, alias="HasErrors")
    has_warnings: Optional[bool] = Field(default=None, alias="HasWarnings")
    job_error: Optional[JobErrorInfo] = Field(default=None, alias="JobError")
    id: int = Field(alias="Id")
