"""Python script runtime implementation for executing and managing python scripts."""

import logging
from typing import Any, Awaitable, Callable, Optional, TypeVar

from ._contracts import (
    UiPathBaseRuntime,
    UiPathErrorCategory,
    UiPathRuntimeContext,
    UiPathRuntimeError,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)
from ._script_executor import ScriptExecutor

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")
AsyncFunc = Callable[[T], Awaitable[R]]


class UiPathRuntime(UiPathBaseRuntime):
    def __init__(self, context: UiPathRuntimeContext, executor: AsyncFunc[Any, Any]):
        self.context = context
        self.executor = executor

    async def cleanup(self) -> None:
        """Cleanup runtime resources."""
        pass

    async def validate(self):
        """Validate runtime context."""
        pass

    async def execute(self) -> Optional[UiPathRuntimeResult]:
        """Execute the Python script with the provided input and configuration.

        Returns:
            Dictionary with execution results

        Raises:
            UiPathRuntimeError: If execution fails
        """
        try:
            script_result = await self.executor(self.context.input_json)

            if self.context.job_id is None:
                logger.info(script_result)

            self.context.result = UiPathRuntimeResult(
                output=script_result, status=UiPathRuntimeStatus.SUCCESSFUL
            )

            return self.context.result

        except Exception as e:
            if isinstance(e, UiPathRuntimeError):
                raise

            raise UiPathRuntimeError(
                "EXECUTION_ERROR",
                "Python script execution failed",
                f"Error: {str(e)}",
                UiPathErrorCategory.SYSTEM,
            ) from e


class UiPathScriptRuntime(UiPathRuntime):
    """Runtime for executing Python scripts."""

    def __init__(self, context: UiPathRuntimeContext, entrypoint: str):
        executor = ScriptExecutor(entrypoint)
        super().__init__(context, executor)

    @classmethod
    def from_context(cls, context: UiPathRuntimeContext):
        """Create runtime instance from context."""
        return UiPathScriptRuntime(context, context.entrypoint or "")
