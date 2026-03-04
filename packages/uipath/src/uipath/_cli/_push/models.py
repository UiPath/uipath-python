"""Models for push command."""

from pydantic import BaseModel, Field


class EvaluatorFileDetails(BaseModel):
    """Details about an evaluator file for push operations."""

    path: str
    custom_evaluator_file_name: str = Field(
        "", description="Name of the custom evaluator file, if available."
    )

    @property
    def is_custom(self) -> bool:
        """Check if this is a custom evaluator."""
        return len(self.custom_evaluator_file_name) > 0
