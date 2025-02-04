from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class Process(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
        json_encoders={datetime: lambda v: v.isoformat() if v else None},
    )

    key: str = Field(alias="Key")
    process_key: str = Field(alias="ProcessKey")
    process_version: str = Field(alias="ProcessVersion")
    is_latest_version: bool = Field(alias="IsLatestVersion")
    is_process_deleted: bool = Field(alias="IsProcessDeleted")
    description: str = Field(alias="Description")
    name: str = Field(alias="Name")
    environment_variables: Optional[str] = Field(
        default=None, alias="EnvironmentVariables"
    )
    process_type: str = Field(alias="ProcessType")
    requires_user_interaction: bool = Field(alias="RequiresUserInteraction")
    is_attended: bool = Field(alias="IsAttended")
    is_compiled: bool = Field(alias="IsCompiled")
    feed_id: str = Field(alias="FeedId")
    job_priority: str = Field(alias="JobPriority")
    specific_priority_value: int = Field(alias="SpecificPriorityValue")
    target_framework: str = Field(alias="TargetFramework")
    id: int = Field(alias="Id")
    retention_action: str = Field(alias="RetentionAction")
    retention_period: int = Field(alias="RetentionPeriod")
    stale_retention_action: str = Field(alias="StaleRetentionAction")
    stale_retention_period: int = Field(alias="StaleRetentionPeriod")
    arguments: Optional[Dict[str, Optional[Any]]] = Field(
        default=None, alias="Arguments"
    )
    tags: List[str] = Field(alias="Tags")
    environment: Optional[str] = Field(default=None, alias="Environment")
    current_version: Optional[Dict[str, Any]] = Field(
        default=None, alias="CurrentVersion"
    )
    entry_point: Optional[Dict[str, Any]] = Field(default=None, alias="EntryPoint")
