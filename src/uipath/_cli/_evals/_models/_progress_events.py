from dataclasses import dataclass
from typing import Any, List, Literal, Union

from uipath._cli._evals._models._evaluation_set import EvaluationItem
from uipath._cli._evals._models._sw_reporting import AgentSnapshot
from uipath.eval.evaluators import BaseEvaluator
from uipath.eval.models import EvalItemResult


@dataclass
class CreateEvalSetRunEvent:
    type: Literal["create_eval_set_run"]
    eval_set_id: str
    agent_snapshot: AgentSnapshot
    no_of_evals: int
    evaluators: List[BaseEvaluator[Any]]


@dataclass
class CreateEvalRunEvent:
    type: Literal["create_eval_run"]
    eval_item: EvaluationItem


@dataclass
class UpdateEvalRunEvent:
    type: Literal["update_eval_run"]
    eval_run_id: str
    eval_results: List[EvalItemResult]
    success: bool
    agent_output: Any
    agent_execution_time: float


@dataclass
class UpdateEvalSetRunEvent:
    type: Literal["update_eval_set_run"]


ProgressEvent = Union[
    CreateEvalSetRunEvent, CreateEvalRunEvent, UpdateEvalRunEvent, UpdateEvalSetRunEvent
]
