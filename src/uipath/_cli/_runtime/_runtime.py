"""Python script runtime implementation for executing and managing python scripts."""

import importlib.util
import inspect
import json
import logging
import os
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional, Type, TypeVar, cast, get_type_hints

from ._contracts import (
    UiPathBaseRuntime,
    UiPathErrorCategory,
    UiPathRuntimeError,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class UiPathRuntime(UiPathBaseRuntime):
    """Runtime for executing Python scripts."""

    async def execute(self) -> Optional[UiPathRuntimeResult]:
        """Execute the Python script with the provided input and configuration.

        Returns:
            Dictionary with execution results

        Raises:
            UiPathRuntimeError: If execution fails
        """
        await self.validate()

        try:
            if self.context.entrypoint is None:
                return None

            script_result = self._execute_python_script(
                self.context.entrypoint, self.context.input_json
            )

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

    async def validate(self) -> None:
        """Validate runtime inputs."""
        if not self.context.entrypoint:
            raise UiPathRuntimeError(
                "ENTRYPOINT_MISSING",
                "No entrypoint specified",
                "Please provide a path to a Python script.",
                UiPathErrorCategory.USER,
            )

        if not os.path.exists(self.context.entrypoint):
            raise UiPathRuntimeError(
                "ENTRYPOINT_NOT_FOUND",
                "Script not found",
                f"Script not found at path {self.context.entrypoint}.",
                UiPathErrorCategory.USER,
            )

        try:
            if self.context.input:
                self.context.input_json = json.loads(self.context.input)
            else:
                self.context.input_json = {}
        except json.JSONDecodeError as e:
            raise UiPathRuntimeError(
                "INPUT_INVALID_JSON",
                "Invalid JSON input",
                f"The input data is not valid JSON: {str(e)}",
                UiPathErrorCategory.USER,
            ) from e

    async def cleanup(self) -> None:
        """Cleanup runtime resources."""
        pass

    def _execute_python_script(self, script_path: str, input_data: Any) -> Any:
        """Execute the Python script with the given input."""
        spec = importlib.util.spec_from_file_location("dynamic_module", script_path)
        if not spec or not spec.loader:
            raise UiPathRuntimeError(
                "IMPORT_ERROR",
                "Module import failed",
                f"Could not load spec for {script_path}",
                UiPathErrorCategory.USER,
            )

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise UiPathRuntimeError(
                "MODULE_EXECUTION_ERROR",
                "Module execution failed",
                f"Error executing module: {str(e)}",
                UiPathErrorCategory.USER,
            ) from e

        for func_name in ["main", "run", "execute"]:
            if hasattr(module, func_name):
                main_func = getattr(module, func_name)
                sig = inspect.signature(main_func)
                params = list(sig.parameters.values())

                # Case 1: No parameters
                if not params:
                    try:
                        result = main_func()
                        return (
                            self._convert_from_class(result)
                            if result is not None
                            else {}
                        )
                    except Exception as e:
                        raise UiPathRuntimeError(
                            "FUNCTION_EXECUTION_ERROR",
                            f"Error executing {func_name} function",
                            f"Error: {str(e)}",
                            UiPathErrorCategory.USER,
                        ) from e

                input_param = params[0]
                input_type = input_param.annotation

                # Case 2: Class or dataclass parameter
                if input_type != inspect.Parameter.empty and (
                    is_dataclass(input_type) or hasattr(input_type, "__annotations__")
                ):
                    try:
                        valid_type = cast(Type[Any], input_type)
                        typed_input = self._convert_to_class(input_data, valid_type)
                        result = main_func(typed_input)
                        return (
                            self._convert_from_class(result)
                            if result is not None
                            else {}
                        )
                    except Exception as e:
                        raise UiPathRuntimeError(
                            "FUNCTION_EXECUTION_ERROR",
                            f"Error executing {func_name} function with typed input",
                            f"Error: {str(e)}",
                            UiPathErrorCategory.USER,
                        ) from e

                # Case 3: Dict parameter
                else:
                    try:
                        result = main_func(input_data)
                        return (
                            self._convert_from_class(result)
                            if result is not None
                            else {}
                        )
                    except Exception as e:
                        raise UiPathRuntimeError(
                            "FUNCTION_EXECUTION_ERROR",
                            f"Error executing {func_name} function with dictionary input",
                            f"Error: {str(e)}",
                            UiPathErrorCategory.USER,
                        ) from e

        raise UiPathRuntimeError(
            "ENTRYPOINT_FUNCTION_MISSING",
            "No entry function found",
            f"No main function (main, run, or execute) found in {script_path}",
            UiPathErrorCategory.USER,
        )

    def _convert_to_class(self, data: Dict[str, Any], cls: Type[T]) -> T:
        """Convert a dictionary to either a dataclass or regular class instance."""
        if is_dataclass(cls):
            field_types = get_type_hints(cls)
            converted_data = {}

            for field_name, field_type in field_types.items():
                if field_name not in data:
                    continue

                value = data[field_name]
                if (
                    is_dataclass(field_type) or hasattr(field_type, "__annotations__")
                ) and isinstance(value, dict):
                    typed_field = cast(Type[Any], field_type)
                    value = self._convert_to_class(value, typed_field)
                converted_data[field_name] = value

            return cast(T, cls(**converted_data))
        else:
            sig = inspect.signature(cls.__init__)
            params = sig.parameters

            init_args = {}

            for param_name, param in params.items():
                if param_name == "self":
                    continue

                if param_name in data:
                    value = data[param_name]
                    param_type = (
                        param.annotation
                        if param.annotation != inspect.Parameter.empty
                        else Any
                    )

                    if (
                        is_dataclass(param_type)
                        or hasattr(param_type, "__annotations__")
                    ) and isinstance(value, dict):
                        typed_param = cast(Type[Any], param_type)
                        value = self._convert_to_class(value, typed_param)

                    init_args[param_name] = value
                elif param.default != inspect.Parameter.empty:
                    init_args[param_name] = param.default

            return cls(**init_args)

    def _convert_from_class(self, obj: Any) -> Dict[str, Any]:
        """Convert a class instance (dataclass or regular) to a dictionary."""
        if obj is None:
            return {}

        if is_dataclass(obj):
            # Make sure obj is an instance, not a class
            if isinstance(obj, type):
                return {}
            return asdict(obj)
        elif hasattr(obj, "__dict__"):
            result = {}
            for key, value in obj.__dict__.items():
                # Skip private attributes
                if not key.startswith("_"):
                    if hasattr(value, "__dict__") or is_dataclass(value):
                        result[key] = self._convert_from_class(value)
                    else:
                        result[key] = value
            return result
        return {} if obj is None else {str(type(obj).__name__): str(obj)}  # Fallback
