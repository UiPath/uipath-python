from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, field_serializer
from typing_extensions import Annotated


class QueueItemPriority(Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class CommitType(Enum):
    ALL_OR_NOTHING = "AllOrNothing"
    STOP_ON_FIRST_FAILURE = "StopOnFirstFailure"
    PROCESS_ALL_INDEPENDENTLY = "ProcessAllIndependently"


class QueueItem(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    @field_serializer("defer_date", "due_date", "risk_sla_date", when_used="json")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            return value.isoformat() if value else None
        return value

    name: str = Field(
        description="The name of the queue into which the item will be added.",
        alias="Name",
    )
    priority: Optional[QueueItemPriority] = Field(
        default=None,
        description="Sets the processing importance for a given item.",
        alias="Priority",
    )
    specific_content: Optional[Dict[str, Any]] = Field(
        default=None,
        description="A collection of key value pairs containing custom data configured in the Add Queue Item activity, in UiPath Studio.",
        alias="SpecificContent",
    )
    defer_date: Optional[datetime] = Field(
        default=None,
        description="The earliest date and time at which the item is available for processing. If empty the item can be processed as soon as possible.",
        alias="DeferDate",
    )
    due_date: Optional[datetime] = Field(
        default=None,
        description="The latest date and time at which the item should be processed. If empty the item can be processed at any given time.",
        alias="DueDate",
    )
    risk_sla_date: Optional[datetime] = Field(
        default=None,
        description="The RiskSla date at time which is considered as risk zone for the item to be processed.",
        alias="RiskSlaDate",
    )
    progress: Optional[str] = Field(
        default=None,
        description="String field which is used to keep track of the business flow progress.",
        alias="Progress",
    )
    source: Optional[
        Annotated[str, Field(min_length=0, strict=True, max_length=20)]
    ] = Field(default=None, description="The Source type of the item.", alias="Source")
    parent_operation_id: Optional[
        Annotated[str, Field(min_length=0, strict=True, max_length=128)]
    ] = Field(
        default=None,
        description="Operation id which started the job.",
        alias="ParentOperationId",
    )


class TransactionItem(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    @field_serializer("defer_date", "due_date", when_used="json")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            return value.isoformat() if value else None
        return value

    name: str = Field(
        description="The name of the queue in which to search for the next item or in which to insert the item before marking it as InProgress and sending it to the robot.",
        alias="Name",
    )
    robot_identifier: Optional[str] = Field(
        default=None,
        description="The unique key identifying the robot that sent the request.",
        alias="RobotIdentifier",
    )
    specific_content: Optional[Dict[str, Any]] = Field(
        default=None,
        description="If not null a new item will be added to the queue with this content before being moved to InProgress state and returned to the robot for processing.  <para />If null the next available item in the list will be moved to InProgress state and returned to the robot for processing.",
        alias="SpecificContent",
    )
    defer_date: Optional[datetime] = Field(
        default=None,
        description="The earliest date and time at which the item is available for processing. If empty the item can be processed as soon as possible.",
        alias="DeferDate",
    )
    due_date: Optional[datetime] = Field(
        default=None,
        description="The latest date and time at which the item should be processed. If empty the item can be processed at any given time.",
        alias="DueDate",
    )
    parent_operation_id: Optional[
        Annotated[str, Field(min_length=0, strict=True, max_length=128)]
    ] = Field(
        default=None,
        description="Operation id which created the queue item.",
        alias="ParentOperationId",
    )


class TransactionItemResult(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )

    @field_serializer("defer_date", "due_date", when_used="json")
    def serialize_datetime(self, value):
        if isinstance(value, datetime):
            return value.isoformat() if value else None
        return value

    is_successful: Optional[bool] = Field(
        default=None,
        description="States if the processing was successful or not.",
        alias="IsSuccessful",
    )
    processing_exception: Optional[Any] = Field(
        default=None, alias="ProcessingException"
    )
    defer_date: Optional[datetime] = Field(
        default=None,
        description="The earliest date and time at which the item is available for processing. If empty the item can be processed as soon as possible.",
        alias="DeferDate",
    )
    due_date: Optional[datetime] = Field(
        default=None,
        description="The latest date and time at which the item should be processed. If empty the item can be processed at any given time.",
        alias="DueDate",
    )
    output: Optional[Dict[str, Any]] = Field(
        default=None,
        description="A collection of key value pairs containing custom data resulted after successful processing.",
        alias="Output",
    )
    analytics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="A collection of key value pairs containing custom data for further analytics processing.",
        alias="Analytics",
    )
    progress: Optional[str] = Field(
        default=None,
        description="String field which is used to keep track of the business flow progress.",
        alias="Progress",
    )
    operation_id: Optional[Annotated[str, Field(strict=True, max_length=128)]] = Field(
        default=None,
        description="The operation id which finished the queue item. Will be saved only if queue item is in final state",
        alias="OperationId",
    )
