"""Models for Orchestrator Jobs."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

class JobErrorInfo(BaseModel):
    """Model representing job error information."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    code: str | None = Field(default=None, alias="Code")
    title: str | None = Field(default=None, alias="Title")
    detail: str | None = Field(default=None, alias="Detail")
    category: str | None = Field(default=None, alias="Category")
    status: int | None = Field(default=None, alias="Status")

class Job(BaseModel):
    """Model representing an orchestrator job."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    key: str | None = Field(default=None, alias="Key")
    start_time: str | None = Field(default=None, alias="StartTime")
    end_time: str | None = Field(default=None, alias="EndTime")
    state: str | None = Field(default=None, alias="State")
    job_priority: str | None = Field(default=None, alias="JobPriority")
    specific_priority_value: int | None = Field(
        default=None, alias="SpecificPriorityValue"
    )
    robot: dict[str, Any] | None = Field(default=None, alias="Robot")
    release: dict[str, Any] | None = Field(default=None, alias="Release")
    resource_overwrites: str | None = Field(default=None, alias="ResourceOverwrites")
    source: str | None = Field(default=None, alias="Source")
    source_type: str | None = Field(default=None, alias="SourceType")
    batch_execution_key: str | None = Field(default=None, alias="BatchExecutionKey")
    info: str | None = Field(default=None, alias="Info")
    creation_time: str | None = Field(default=None, alias="CreationTime")
    creator_user_id: int | None = Field(default=None, alias="CreatorUserId")
    last_modification_time: str | None = Field(
        default=None, alias="LastModificationTime"
    )
    last_modifier_user_id: int | None = Field(
        default=None, alias="LastModifierUserId"
    )
    deletion_time: str | None = Field(default=None, alias="DeletionTime")
    deleter_user_id: int | None = Field(default=None, alias="DeleterUserId")
    is_deleted: bool | None = Field(default=None, alias="IsDeleted")
    input_arguments: str | None = Field(default=None, alias="InputArguments")
    input_file: str | None = Field(default=None, alias="InputFile")
    output_arguments: str | None = Field(default=None, alias="OutputArguments")
    output_file: str | None = Field(default=None, alias="OutputFile")
    host_machine_name: str | None = Field(default=None, alias="HostMachineName")
    has_errors: bool | None = Field(default=None, alias="HasErrors")
    has_warnings: bool | None = Field(default=None, alias="HasWarnings")
    job_error: JobErrorInfo | None = Field(default=None, alias="JobError")
    id: int = Field(alias="Id")
