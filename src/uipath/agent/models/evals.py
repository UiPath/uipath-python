"""Agent Evaluation Models.

These models extend the base agent models with evaluation and simulation-specific fields.
"""

from typing import List, Optional

from pydantic import Field

from uipath._cli._evals._models._evaluation_set import EvaluationSet
from uipath._cli._evals._models._evaluator import Evaluator
from uipath._cli._evals._models._mocks import ExampleCall
from uipath.agent.models.agent import (
    AgentDefinition,
    AgentEscalationChannelProperties,
    AgentIntegrationToolProperties,
    AgentProcessToolProperties,
    BaseResourceProperties,
)


class AgentEvalResourceProperties(BaseResourceProperties):
    """Resource properties with simulation support."""

    example_calls: Optional[List[ExampleCall]] = Field(None, alias="exampleCalls")


class AgentEvalProcessToolProperties(AgentProcessToolProperties):
    """Process tool properties with simulation support."""

    example_calls: Optional[List[ExampleCall]] = Field(None, alias="exampleCalls")


class AgentEvalIntegrationToolProperties(AgentIntegrationToolProperties):
    """Integration tool properties with simulation support."""

    example_calls: Optional[List[ExampleCall]] = Field(None, alias="exampleCalls")


class AgentEvalEscalationChannelProperties(AgentEscalationChannelProperties):
    """Escalation channel properties with simulation support."""

    example_calls: Optional[List[ExampleCall]] = Field(None, alias="exampleCalls")


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
