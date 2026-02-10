from uipath.eval.evaluators import (
    BaseEvaluationCriteria,
    BaseEvaluator,
    BaseEvaluatorConfig,
)
from uipath.eval.models import AgentExecution, EvaluationResult, NumericEvaluationResult


class AttachmentCreatedEvaluationCriteria(BaseEvaluationCriteria):
    """Evaluation criteria for the attachment created evaluator."""

    attachment_name: str = "processed_output.txt"


class AttachmentCreatedEvaluatorConfig(
    BaseEvaluatorConfig[AttachmentCreatedEvaluationCriteria]
):
    """Configuration for the attachment created evaluator."""

    name: str = "AttachmentCreatedEvaluator"
    default_evaluation_criteria: AttachmentCreatedEvaluationCriteria = (
        AttachmentCreatedEvaluationCriteria()
    )


class AttachmentCreatedEvaluator(
    BaseEvaluator[
        AttachmentCreatedEvaluationCriteria, AttachmentCreatedEvaluatorConfig, str
    ]
):
    """A custom evaluator that checks if the agent successfully created an output attachment."""

    @classmethod
    def get_evaluator_id(cls) -> str:
        return "AttachmentCreatedEvaluator"

    async def evaluate(
        self,
        agent_execution: AgentExecution,
        evaluation_criteria: AttachmentCreatedEvaluationCriteria,
    ) -> EvaluationResult:
        # Check if the agent created an attachment by looking for:
        # 1. Span with name containing "create_attachment"
        # 2. Or output containing attachment ID/information

        attachment_created = False

        # Look for attachment creation in traces
        for span in agent_execution.agent_trace:
            # Check span name for attachment operations
            if "attachment" in span.name.lower() or "create" in span.name.lower():
                attachment_created = True
                break

            # Check span attributes for attachment information
            if span.attributes:
                for attr_key, attr_value in span.attributes.items():
                    if isinstance(attr_value, str):
                        if (
                            "attachment" in attr_key.lower()
                            or evaluation_criteria.attachment_name in attr_value
                        ):
                            attachment_created = True
                            break

            if attachment_created:
                break

        # Also check if output contains attachment information
        if not attachment_created and agent_execution.agent_output:
            output_str = str(agent_execution.agent_output)
            if (
                "attachment" in output_str.lower()
                or evaluation_criteria.attachment_name in output_str
            ):
                attachment_created = True

        return NumericEvaluationResult(
            score=float(attachment_created),
            details=self.validate_justification(
                f"Attachment '{evaluation_criteria.attachment_name}' {'found' if attachment_created else 'not found'}"
            ),
        )
