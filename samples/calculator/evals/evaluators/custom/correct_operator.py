import json

from uipath.eval.evaluators import BaseEvaluator, BaseEvaluationCriteria, BaseEvaluatorConfig
from uipath.eval.models import AgentExecution, EvaluationResult, NumericEvaluationResult
from opentelemetry.sdk.trace import ReadableSpan

class CorrectOperatorEvaluationCriteria(BaseEvaluationCriteria):
    """Evaluation criteria for the contains evaluator."""

    operator: str

class CorrectOperatorEvaluatorConfig(BaseEvaluatorConfig[CorrectOperatorEvaluationCriteria]):
    """Configuration for the contains evaluator."""

    name: str = "CorrectOperatorEvaluator"
    negated: bool = False
    default_evaluation_criteria: CorrectOperatorEvaluationCriteria = CorrectOperatorEvaluationCriteria(operator="+")

class CorrectOperatorEvaluator(BaseEvaluator[CorrectOperatorEvaluationCriteria, CorrectOperatorEvaluatorConfig, type(None)]):
    """A custom evaluator that checks if the correct operator is being used by the agent """

    def extract_operator_from_spans(self, agent_trace: list[ReadableSpan]) -> str:
        for span in agent_trace:
            if span.name == "track_operator":
                if span.attributes:
                    input_value_as_str = span.attributes.get("input.value", "{}")
                    assert isinstance(input_value_as_str, str)
                    input_value = json.loads(input_value_as_str)
                    return input_value.get("operator")
        raise Exception(f"No 'track_operator' span found")


    @classmethod
    def get_evaluator_id(cls) -> str:
        return "CorrectOperatorEvaluator"


    async def evaluate(self, agent_execution: AgentExecution, evaluation_criteria: CorrectOperatorEvaluationCriteria) -> EvaluationResult:
        actual_operator = self.extract_operator_from_spans(agent_execution.agent_trace)
        print(actual_operator)
        is_expected_operator = evaluation_criteria.operator == actual_operator
        if self.evaluator_config.negated:
            is_expected_operator = not is_expected_operator
        return NumericEvaluationResult(
            score=float(is_expected_operator),
        )
