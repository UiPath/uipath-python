from opentelemetry.sdk.trace import ReadableSpan
from pydantic import BaseModel, ConfigDict

from uipath._cli._runtime._contracts import UiPathRuntimeResult


class UiPathEvalRunExecutionOutput(BaseModel):
    """Result of a single agent response."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    execution_time: float
    spans: list[ReadableSpan]
    result: UiPathRuntimeResult
