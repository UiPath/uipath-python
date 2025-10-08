import enum
import logging
from typing import Any, List, Optional, Union

from opentelemetry.sdk.trace import ReadableSpan
from pydantic import BaseModel, ConfigDict, model_validator

from uipath._cli._evals._models._evaluation_set import EvaluationItem
from uipath.eval.models import EvalItemResult


class EvaluationEvents(str, enum.Enum):
    CREATE_EVAL_SET_RUN = "create_eval_set_run"
    CREATE_EVAL_RUN = "create_eval_run"
    UPDATE_EVAL_SET_RUN = "update_eval_set_run"
    UPDATE_EVAL_RUN = "update_eval_run"


class EvalSetRunCreatedEvent(BaseModel):
    execution_id: str
    entrypoint: str
    eval_set_id: str
    no_of_evals: int
    evaluators: List[Any]


class EvalRunCreatedEvent(BaseModel):
    execution_id: str
    eval_item: EvaluationItem


class EvalItemExceptionDetails(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    runtime_exception: bool = False
    exception: Exception


class EvalRunUpdatedEvent(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    execution_id: str
    eval_item: EvaluationItem
    eval_results: List[EvalItemResult]
    success: bool
    agent_output: Any
    agent_execution_time: float
    spans: List[ReadableSpan]
    logs: List[logging.LogRecord]
    exception_details: Optional[EvalItemExceptionDetails] = None

    @model_validator(mode="after")
    def validate_exception_details(self):
        if not self.success and self.exception_details is None:
            raise ValueError("exception_details must be provided when success is False")
        return self


class EvalSetRunUpdatedEvent(BaseModel):
    execution_id: str
    evaluator_scores: dict[str, float]


ProgressEvent = Union[
    EvalSetRunCreatedEvent,
    EvalRunCreatedEvent,
    EvalRunUpdatedEvent,
    EvalSetRunUpdatedEvent,
]
