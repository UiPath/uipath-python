from pydantic import BaseModel

from uipath.eval.models.models import EvaluatorCategory, EvaluatorType


class EvaluatorBaseParams(BaseModel):
    """Parameters for initializing the base evaluator."""

    id: str
    category: EvaluatorCategory
    evaluator_type: EvaluatorType
    name: str
    description: str
    created_at: str
    updated_at: str
    target_output_key: str
