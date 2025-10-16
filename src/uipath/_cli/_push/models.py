from pydantic import BaseModel, Field


class EvaluatorFileDetails(BaseModel):
    path: str
    custom_evaluator_file_name: str = Field(
        "", description="Name of the custom evaluator file, if available."
    )

    @property
    def is_custom(self) -> bool:
        return len(self.custom_evaluator_file_name) > 0
