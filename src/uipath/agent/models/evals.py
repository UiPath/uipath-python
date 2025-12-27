"""Agent Evaluation Models.

These models extend the base agent models with evaluation and simulation-specific fields.
"""

from typing import List, Optional

from pydantic import Field

from uipath._cli._evals._models._evaluation_set import EvaluationSet
from uipath._cli._evals._models._evaluator import Evaluator
from uipath.agent.models.agent import (
    AgentDefinition,
)


class AgentEvalsDefinition(AgentDefinition):
    """Agent definition with evaluation sets and evaluators support."""

    evaluation_sets: Optional[List[EvaluationSet]] = Field(
        None,
        alias="evaluationSets",
        description="List of agent evaluation sets",
    )
    evaluators: Optional[List[Evaluator]] = Field(
        None, description="List of agent evaluators"
    )
