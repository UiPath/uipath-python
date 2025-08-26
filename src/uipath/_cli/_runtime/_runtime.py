"""Python script runtime implementation for executing and managing python scripts."""

import importlib.util
import inspect
import json
import logging
import os
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, Optional, Type, TypeVar, cast, get_type_hints

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel

from uipath.tracing import LlmOpsHttpExporter

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

        shutdown_provider = False
        trace_provider: Optional[TracerProvider] = None
        span_processor: Optional[BatchSpanProcessor] = None

        if self.context.trace_context.enabled:
            trace_provider = trace.get_tracer_provider()
            if not trace_provider:
                trace_provider = TracerProvider()
                trace.set_tracer_provider(trace_provider)
                shutdown_provider = True
            span_processor = BatchSpanProcessor(LlmOpsHttpExporter())
            trace_provider.add_span_processor(span_processor)

        try:
            if self.context.entrypoint is None:
                return None

            script_result = await self._execute_python_script(
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

        finally:
            if self.context.trace_context.enabled:
                await span_processor.force_flush()
                # Only shutdown if we created the provider
                if shutdown_provider:
                    await trace_provider.shutdown()

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

    async def _execute_python_script(self, script_path: str, input_data: Any) -> Any:
        """Execute the Python script with the given input."""
        # parent_span = trace.get_current_span()
        # ctx = trace.set_span_in_context(parent_span)

        # print(f"Before module execution - Current span: {parent_span}")
        # print(f"Current span attributes: {getattr(parent_span, 'attributes', {})}")

        spec = importlib.util.spec_from_file_location("dynamic_module", script_path)
        if not spec or not spec.loader:
            raise UiPathRuntimeError(
                "IMPORT_ERROR",
                "Module import failed",
                f"Could not load spec for {script_path}",
                UiPathErrorCategory.USER,
            )

        module = importlib.util.module_from_spec(spec)

        # Attach the context BEFORE any module operations
        # token = context_api.attach(ctx)

        try:
            # print("Executing module with context attached")
            spec.loader.exec_module(module)

            # active_span = trace.get_current_span()
            # print(f"After module execution - Active span: {active_span}")

            # Execute the function while context is still attached
            for func_name in ["main", "run", "execute"]:
                if hasattr(module, func_name):
                    main_func = getattr(module, func_name)
                    sig = inspect.signature(main_func)
                    params = list(sig.parameters.values())
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
                                "FUNCTION_EXECUTION_ERROR",
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
                            "FUNCTION_EXECUTION_ERROR",
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
                                "FUNCTION_EXECUTION_ERROR",
                                f"Error executing {func_name} function with dictionary input",
                                f"Error: {str(e)}",
                                UiPathErrorCategory.USER,
                            ) from e

            # If we get here, no main function was found
            raise UiPathRuntimeError(
                "ENTRYPOINT_FUNCTION_MISSING",
                "No entry function found",
                f"No main function (main, run, or execute) found in {script_path}",
                UiPathErrorCategory.USER,
            )

        except Exception as e:
            # Handle module execution errors
            if isinstance(e, UiPathRuntimeError):
                raise
            raise UiPathRuntimeError(
                "MODULE_EXECUTION_ERROR",
                "Module execution failed",
                f"Error executing module: {str(e)}",
                UiPathErrorCategory.USER,
            ) from e

        # finally:
        # Only detach the context at the very end, after all operations
        # context_api.detach(token)

    def _convert_to_class(self, data: Dict[str, Any], cls: Type[T]) -> T:
        """Convert a dictionary to either a dataclass, Pydantic model, or regular class instance."""
        # Handle Pydantic models
        try:
            if inspect.isclass(cls) and issubclass(cls, BaseModel):
                return cast(T, cls.model_validate(data))
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

            return cast(T, cls(**converted_data))

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
