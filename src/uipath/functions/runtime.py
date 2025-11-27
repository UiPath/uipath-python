"""UiPath Function Runtime - wrapper for executing Python functions."""

import importlib.util
import inspect
import logging
import sys
import uuid
from dataclasses import is_dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, AsyncGenerator, Callable, Type, cast, get_type_hints

from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeEvent,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)
from uipath.runtime.errors import (
    UiPathErrorCategory,
    UiPathErrorCode,
    UiPathErrorContract,
    UiPathRuntimeError,
)
from uipath.runtime.schema import UiPathRuntimeSchema

from .schema_gen import get_type_schema
from .type_conversion import (
    convert_from_class,
    convert_to_class,
    is_pydantic_model,
)

logger = logging.getLogger(__name__)


class UiPathFunctionsRuntime:
    """Runtime wrapper for a single Python function with full script executor compatibility."""

    def __init__(self, file_path: str, function_name: str, entrypoint_name: str):
        """Initialize the function runtime."""
        self.file_path = Path(file_path)
        self.function_name = function_name
        self.entrypoint_name = entrypoint_name
        self._function: Callable[..., Any] | None = None
        self._module: ModuleType | None = None

    def _load_module(self) -> None:
        """Load the Python module containing the function."""
        if self._module is not None:
            return

        spec = importlib.util.spec_from_file_location(
            "dynamic_module", str(self.file_path)
        )
        if not spec or not spec.loader:
            raise UiPathRuntimeError(
                UiPathErrorCode.IMPORT_ERROR,
                "Module import failed",
                f"Could not load spec for {self.file_path}",
                UiPathErrorCategory.USER,
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules["dynamic_module"] = module
        self._module = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise UiPathRuntimeError(
                UiPathErrorCode.MODULE_EXECUTION_ERROR,
                "Module execution failed",
                f"Error executing module: {e}",
                UiPathErrorCategory.USER,
            ) from e

    def _load_function(self) -> Callable[..., Any]:
        """Load the function from the module."""
        if self._function is not None:
            return self._function

        self._load_module()

        if not hasattr(self._module, self.function_name):
            raise UiPathRuntimeError(
                UiPathErrorCode.ENTRYPOINT_FUNCTION_MISSING,
                "Function not found",
                f"Function '{self.function_name}' not found in {self.file_path}",
                UiPathErrorCategory.USER,
            )

        self._function = getattr(self._module, self.function_name)
        return self._function

    async def _execute_function(
        self, func: Callable[..., Any], input_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute function with proper input conversion and error handling."""
        sig = inspect.signature(func)
        params = list(sig.parameters.values())
        is_async = inspect.iscoroutinefunction(func)

        # No parameters - call without args
        if not params:
            result = await func() if is_async else func()
            return convert_from_class(result) if result is not None else {}

        # Get first parameter info
        input_param = params[0]
        input_type = input_param.annotation

        # Typed parameter (class, dataclass, or Pydantic)
        if input_type != inspect.Parameter.empty and (
            is_dataclass(input_type)
            or is_pydantic_model(input_type)
            or (inspect.isclass(input_type) and hasattr(input_type, "__annotations__"))
        ):
            typed_input = convert_to_class(input_data, cast(Type[Any], input_type))
            result = await func(typed_input) if is_async else func(typed_input)
        else:
            # Dict/untyped parameter
            result = await func(input_data) if is_async else func(input_data)

        return convert_from_class(result) if result is not None else {}

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        """Execute the function with the given input."""
        try:
            func = self._load_function()
            output = await self._execute_function(func, input or {})

            return UiPathRuntimeResult(
                output=output,
                status=UiPathRuntimeStatus.SUCCESSFUL,
            )

        except UiPathRuntimeError:
            raise
        except Exception as e:
            logger.exception(f"Function execution failed: {e}")
            return UiPathRuntimeResult(
                output=None,
                status=UiPathRuntimeStatus.FAULTED,
                error=UiPathErrorContract(
                    code=UiPathErrorCode.FUNCTION_EXECUTION_ERROR,
                    category=UiPathErrorCategory.USER,
                    title=f"Function execution failed: {self.function_name}",
                    detail=str(e),
                ),
            )

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        """Stream execution results (functions don't support streaming, returns single result)."""
        result = await self.execute(input, options)
        yield result

    async def get_schema(self) -> UiPathRuntimeSchema:
        """Get schema for the function."""
        func = self._load_function()
        hints = get_type_hints(func)
        sig = inspect.signature(func)

        # Determine input schema
        if not sig.parameters:
            input_schema = {}
        else:
            input_param_name = next(iter(sig.parameters))
            input_schema = get_type_schema(hints.get(input_param_name))

        # Determine output schema
        output_schema = get_type_schema(hints.get("return"))

        return UiPathRuntimeSchema(
            filePath=self.entrypoint_name,
            uniqueId=str(uuid.uuid4()),
            type="agent",
            input=input_schema,
            output=output_schema,
        )

    async def dispose(self) -> None:
        """Cleanup resources."""
        self._function = None
        if "dynamic_module" in sys.modules:
            del sys.modules["dynamic_module"]
        self._module = None
