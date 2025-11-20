from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Process(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    key: str = Field(alias="Key")
    process_key: str = Field(alias="ProcessKey")
    process_version: str = Field(alias="ProcessVersion")
    is_latest_version: bool = Field(alias="IsLatestVersion")
    is_process_deleted: bool = Field(alias="IsProcessDeleted")
    description: Optional[str] = Field(default=None, alias="Description")
    name: str = Field(alias="Name")
    environment_variables: Optional[str] = Field(
        default=None, alias="EnvironmentVariables"
    )
    process_type: str = Field(alias="ProcessType")
    requires_user_interaction: Optional[bool] = Field(
        default=None, alias="RequiresUserInteraction"
    )
    is_attended: Optional[bool] = Field(default=None, alias="IsAttended")
    is_compiled: Optional[bool] = Field(default=None, alias="IsCompiled")
    feed_id: Optional[str] = Field(default=None, alias="FeedId")
    job_priority: Optional[str] = Field(default=None, alias="JobPriority")
    specific_priority_value: Optional[int] = Field(
        default=None, alias="SpecificPriorityValue"
    )
    target_framework: Optional[str] = Field(default=None, alias="TargetFramework")
    id: int = Field(alias="Id")
    retention_action: Optional[str] = Field(default=None, alias="RetentionAction")
    retention_period: Optional[int] = Field(default=None, alias="RetentionPeriod")
    stale_retention_action: Optional[str] = Field(
        default=None, alias="StaleRetentionAction"
    )
    stale_retention_period: Optional[int] = Field(
        default=None, alias="StaleRetentionPeriod"
    )
    arguments: Optional[Dict[str, Optional[Any]]] = Field(
        default=None, alias="Arguments"
    )
    tags: Optional[List[str]] = Field(default=None, alias="Tags")
    environment: Optional[str] = Field(default=None, alias="Environment")
    current_version: Optional[Dict[str, Any]] = Field(
        default=None, alias="CurrentVersion"
    )
    entry_point: Optional[Dict[str, Any]] = Field(default=None, alias="EntryPoint")
