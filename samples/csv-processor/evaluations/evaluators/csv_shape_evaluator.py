from uipath.eval.evaluators import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
)
from uipath.eval.models import AgentExecution, EvaluationResult, NumericEvaluationResult


class CSVShapeEvaluationCriteria(BaseEvaluationCriteria):
    """Evaluation criteria for the CSV shape evaluator."""

    expected_rows: int
    expected_columns: int


class CSVShapeEvaluatorConfig(BaseEvaluatorConfig[CSVShapeEvaluationCriteria]):
    """Configuration for the CSV shape evaluator."""

    name: str = "CSVShapeEvaluator"
    default_evaluation_criteria: CSVShapeEvaluationCriteria = (
        CSVShapeEvaluationCriteria(expected_rows=1, expected_columns=1)
    )


class CSVShapeEvaluator(
    BaseEvaluator[CSVShapeEvaluationCriteria, CSVShapeEvaluatorConfig, None]
):
    """A custom evaluator that checks if the CSV shape information is correct in the output attachment."""

    @classmethod
    def get_evaluator_id(cls) -> str:
        return "CSVShapeEvaluator"

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: CSVShapeEvaluationCriteria,
    ) -> EvaluationResult:
        # The agent prints: "CSV shape (rows, columns)\nCSV columns [...]"
        # We need to find this in the captured output

        expected_shape = f"({evaluation_criteria.expected_rows}, {evaluation_criteria.expected_columns})"
        shape_found = False

        # Check agent traces (where print output is captured)
        for span in agent_execution.agent_trace:
            # Check span attributes
            if span.attributes:
                for attr_value in span.attributes.values():
                    if isinstance(attr_value, str) and expected_shape in attr_value:
                        shape_found = True
                        break

            # Check span events (where stdout might be captured)
            if hasattr(span, 'events') and span.events:
                for event in span.events:
                    if hasattr(event, 'attributes') and event.attributes:
                        for attr_value in event.attributes.values():
                            if isinstance(attr_value, str) and expected_shape in attr_value:
                                shape_found = True
                                break

            if shape_found:
                break

        # Check agent output
        if not shape_found and agent_execution.agent_output:
            output_str = str(agent_execution.agent_output)
            shape_found = expected_shape in output_str

        return NumericEvaluationResult(
            score=float(shape_found),
        )
