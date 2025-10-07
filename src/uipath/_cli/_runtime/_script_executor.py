"""Python script runtime implementation for executing and managing python scripts."""

import importlib.util
import inspect
import os
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Type, TypeVar, cast, get_type_hints

from pydantic import BaseModel

from ._contracts import UiPathErrorCategory, UiPathErrorCode, UiPathRuntimeError

T = TypeVar("T")


class ScriptExecutor:
    def __init__(self, entrypoint: str):
        self.entrypoint = entrypoint
        self.validate_entrypoint()

    async def __call__(self, input: Any) -> Any:
        return await self._execute_python_script(input)

    def validate_entrypoint(self) -> None:
        """Validate runtime inputs."""
        if not self.entrypoint:
            raise UiPathRuntimeError(
                UiPathErrorCode.ENTRYPOINT_MISSING,
                "No entrypoint specified",
                "Please provide a path to a Python script.",
                UiPathErrorCategory.USER,
            )

        if not os.path.exists(self.entrypoint):
            raise UiPathRuntimeError(
                UiPathErrorCode.ENTRYPOINT_NOT_FOUND,
                "Script not found",
                f"Script not found at path {self.entrypoint}.",
                UiPathErrorCategory.USER,
            )

    async def _execute_python_script(self, input_data: Any) -> Any:
        """Execute the Python script with the given input."""
        spec = importlib.util.spec_from_file_location("dynamic_module", self.entrypoint)
        if not spec or not spec.loader:
            raise UiPathRuntimeError(
                UiPathErrorCode.IMPORT_ERROR,
                "Module import failed",
                f"Could not load spec for {self.entrypoint}",
                UiPathErrorCategory.USER,
            )

        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as e:
            raise UiPathRuntimeError(
                UiPathErrorCode.MODULE_EXECUTION_ERROR,
                "Module execution failed",
                f"Error executing module: {str(e)}",
                UiPathErrorCategory.USER,
            ) from e

        for func_name in ["main", "run", "execute"]:
            if hasattr(module, func_name):
                main_func = getattr(module, func_name)
                sig = inspect.signature(main_func)
                params = list(sig.parameters.values())

                # Check if the function is asynchronous
                is_async = inspect.iscoroutinefunction(main_func)

                # Case 1: No parameters
                if not params:
                    try:
                        result = await main_func() if is_async else main_func()
                        return (
                            self._convert_from_class(result)
                            if result is not None
                            else {}
                        )
                    except Exception as e:
                        raise UiPathRuntimeError(
                            UiPathErrorCode.FUNCTION_EXECUTION_ERROR,
                            f"Error executing {func_name} function",
                            f"Error: {str(e)}",
                            UiPathErrorCategory.USER,
                        ) from e

                input_param = params[0]
                input_type = input_param.annotation

                # Case 2: Class, dataclass, or Pydantic model parameter
                if input_type != inspect.Parameter.empty and (
                    is_dataclass(input_type)
                    or self._is_pydantic_model(input_type)
                    or hasattr(input_type, "__annotations__")
                ):
                    try:
                        valid_type = cast(Type[Any], input_type)
                        typed_input = self._convert_to_class(input_data, valid_type)
                        result = (
                            await main_func(typed_input)
                            if is_async
                            else main_func(typed_input)
                        )
                        return (
                            self._convert_from_class(result)
                            if result is not None
                            else {}
                        )
                    except Exception as e:
                        raise UiPathRuntimeError(
                            UiPathErrorCode.FUNCTION_EXECUTION_ERROR,
                            f"Error executing {func_name} function with typed input",
                            f"Error: {str(e)}",
                            UiPathErrorCategory.USER,
                        ) from e

                # Case 3: Dict parameter
                else:
                    try:
                        result = (
                            await main_func(input_data)
                            if is_async
                            else main_func(input_data)
                        )
                        return (
                            self._convert_from_class(result)
                            if result is not None
                            else {}
                        )
                    except Exception as e:
                        raise UiPathRuntimeError(
                            UiPathErrorCode.FUNCTION_EXECUTION_ERROR,
                            f"Error executing {func_name} function with dictionary input",
                            f"Error: {str(e)}",
                            UiPathErrorCategory.USER,
                        ) from e

        raise UiPathRuntimeError(
            UiPathErrorCode.ENTRYPOINT_FUNCTION_MISSING,
            "No entry function found",
            f"No main function (main, run, or execute) found in {self.entrypoint}",
            UiPathErrorCategory.USER,
        )

    def _convert_to_class(self, data: Dict[str, Any], cls: Type[T]) -> T:
        """Convert a dictionary to either a dataclass, Pydantic model, or regular class instance."""
        # Handle Pydantic models
        try:
            if inspect.isclass(cls) and issubclass(cls, BaseModel):
                return cls.model_validate(data)
        except TypeError:
            # issubclass can raise TypeError if cls is not a class
            pass

        # Handle dataclasses
        if is_dataclass(cls):
            field_types = get_type_hints(cls)
            converted_data = {}

            for field_name, field_type in field_types.items():
                if field_name not in data:
                    continue

                value = data[field_name]
                if (
                    is_dataclass(field_type)
                    or self._is_pydantic_model(field_type)
                    or hasattr(field_type, "__annotations__")
                ) and isinstance(value, dict):
                    typed_field = cast(Type[Any], field_type)
                    value = self._convert_to_class(value, typed_field)
                converted_data[field_name] = value

            return cls(**converted_data)

        # Handle regular classes
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
                        or self._is_pydantic_model(param_type)
                        or hasattr(param_type, "__annotations__")
                    ) and isinstance(value, dict):
                        typed_param = cast(Type[Any], param_type)
                        value = self._convert_to_class(value, typed_param)

                    init_args[param_name] = value
                elif param.default != inspect.Parameter.empty:
                    init_args[param_name] = param.default

            return cls(**init_args)

    def _is_pydantic_model(self, cls: Type[Any]) -> bool:
        """Safely check if a class is a Pydantic model."""
        try:
            return inspect.isclass(cls) and issubclass(cls, BaseModel)
        except TypeError:
            # issubclass can raise TypeError if cls is not a class
            return False

    def _convert_from_class(self, obj: Any) -> Dict[str, Any]:
        """Convert a class instance (dataclass, Pydantic model, or regular) to a dictionary."""
        if obj is None:
            return {}

        # Handle Pydantic models
        if isinstance(obj, BaseModel):
            return obj.model_dump()

        # Handle dataclasses
        elif is_dataclass(obj):
            # Make sure obj is an instance, not a class
            if isinstance(obj, type):
                return {}
            return asdict(obj)

        # Handle regular classes
        elif hasattr(obj, "__dict__"):
            result = {}
            for key, value in obj.__dict__.items():
                # Skip private attributes
                if not key.startswith("_"):
                    if (
                        isinstance(value, BaseModel)
                        or hasattr(value, "__dict__")
                        or is_dataclass(value)
                    ):
                        result[key] = self._convert_from_class(value)
                    else:
                        result[key] = value
            return result
        return {} if obj is None else {str(type(obj).__name__): str(obj)}  # Fallback
