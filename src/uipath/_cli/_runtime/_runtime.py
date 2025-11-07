"""Python script runtime implementation for executing and managing python scripts."""

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, TypeVar

from typing_extensions import override

from .._utils._console import ConsoleLogger
from .._utils._input_args import generate_args
from .._utils._parse_ast import generate_bindings  # type: ignore[attr-defined]
from ..models.runtime_schema import Bindings, Entrypoint
from ._contracts import (
    UiPathBaseRuntime,
    UiPathErrorCategory,
    UiPathErrorCode,
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

            self.context.result = UiPathRuntimeResult(
                output=script_result, status=UiPathRuntimeStatus.SUCCESSFUL
            )

            return self.context.result

        except Exception as e:
            if isinstance(e, UiPathRuntimeError):
                raise

            raise UiPathRuntimeError(
                UiPathErrorCode.EXECUTION_ERROR,
                "Python script execution failed",
                f"Error: {str(e)}",
                UiPathErrorCategory.SYSTEM,
            ) from e


console = ConsoleLogger()


def get_user_script(directory: str, entrypoint: Optional[str] = None) -> Optional[str]:
    """Find the Python script to process."""
    if entrypoint:
        script_path = os.path.join(directory, entrypoint)
        if not os.path.isfile(script_path):
            console.error(
                f"The {entrypoint} file does not exist in the current directory."
            )
            return None
        return script_path

    python_files = [f for f in os.listdir(directory) if f.endswith(".py")]

    if not python_files:
        console.error(
            "No python files found in the current directory.\nPlease specify the entrypoint: `uipath init <entrypoint_path>`"
        )
        return None
    elif len(python_files) == 1:
        return os.path.join(directory, python_files[0])
    else:
        console.error(
            "Multiple python files found in the current directory.\nPlease specify the entrypoint: `uipath init <entrypoint_path>`"
        )
        return None


class UiPathScriptRuntime(UiPathRuntime):
    """Runtime for executing Python scripts."""

    def __init__(self, context: UiPathRuntimeContext, entrypoint: str):
        executor = ScriptExecutor(entrypoint)
        super().__init__(context, executor)

    @classmethod
    def from_context(cls, context: UiPathRuntimeContext):
        """Create runtime instance from context."""
        return UiPathScriptRuntime(context, context.entrypoint or "")

    @override
    async def get_bindings(self) -> Bindings:
        """Get binding resources for script runtime.

        Returns: A bindings object.
        """
        working_dir = self.context.runtime_dir or os.getcwd()
        script_path = get_user_script(working_dir, entrypoint=self.context.entrypoint)
        bindings = generate_bindings(script_path)
        return bindings

    @override
    async def get_entrypoint(self) -> Entrypoint:
        working_dir = self.context.runtime_dir or os.getcwd()
        script_path = get_user_script(working_dir, entrypoint=self.context.entrypoint)
        if not script_path:
            raise ValueError("Entrypoint not found.")
        relative_path = Path(script_path).relative_to(working_dir).as_posix()
        args = generate_args(script_path)
        return Entrypoint(
            file_path=relative_path,  # type: ignore[call-arg] # This exists
            unique_id=str(uuid.uuid4()),
            type="agent",
            input=args["input"],
            output=args["output"],
        )
