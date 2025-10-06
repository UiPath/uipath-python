from pydantic import BaseModel

from uipath.eval.models.models import LegacyEvaluatorCategory, LegacyEvaluatorType


class EvaluatorBaseParams(BaseModel):
    """Parameters for initializing the base evaluator."""

    id: str
    category: LegacyEvaluatorCategory
    evaluator_type: LegacyEvaluatorType
    name: str
    description: str
    created_at: str
    updated_at: str
    target_output_key: str
