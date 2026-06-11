"""Shared models for StudioWeb evaluation reporting."""

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from uipath.eval.models import EvalItemResult


class EvaluationStatus(IntEnum):
    PENDING = 0
    IN_PROGRESS = 1
    COMPLETED = 2
    FAILED = 3


class StudioWebProgressItem(BaseModel):
    eval_run_id: str
    eval_results: list[EvalItemResult]
    success: bool
    agent_output: dict[str, Any]
    agent_execution_time: float


class StudioWebAgentSnapshot(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
