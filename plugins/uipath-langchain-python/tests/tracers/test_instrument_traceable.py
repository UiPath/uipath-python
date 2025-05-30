import asyncio
import inspect
from unittest.mock import patch

import pytest

from uipath_langchain.tracers._instrument_traceable import (
    _create_traced_wrapper,
    format_args_for_trace,
)


# Test functions of different types
def sample_sync_function(x, y):
    return x + y


async def sample_async_function(x, y):
    await asyncio.sleep(0.01)  # Small delay to simulate async work
    return x + y


def sample_generator_function(items):
    for item in items:
        yield item * 2


async def sample_async_generator_function(items):
    for item in items:
        await asyncio.sleep(0.01)  # Small delay to simulate async work
        yield item * 2


# Helper processor functions (renamed to not start with "test_")
def sample_input_processor(inputs):
    inputs["processed"] = True
    return inputs


def sample_output_processor(outputs):
    if isinstance(outputs, list):
        return [f"processed_{output}" for output in outputs]
    return f"processed_{outputs}"


class TestCreateTracedWrapper:
    @patch("uipath_langchain.tracers._instrument_traceable.dispatch_trace_event")
    def test_sync_wrapper(self, mock_dispatch):
        # Create a traced wrapper for a sync function
        wrapped = _create_traced_wrapper(
            func=sample_sync_function,
            func_name="test_sync",
            run_type="test",
            span_type="test_span",
            tags=["test_tag"],
            metadata={"test_meta": "value"},
        )

        # Call the wrapped function
        result = wrapped(3, 4)

        # Verify the result
        assert result == 7

        # Verify dispatch_trace_event was called twice (call + completion)
        assert mock_dispatch.call_count == 2

        # Check first call (function call)
        # First [0] gets the first call, second [0] gets positional args, [1] would get kwargs
        call_args = mock_dispatch.call_args_list[0][0]
        assert call_args[0] == "test_sync"  # func_name
        assert call_args[1] == {"x": 3, "y": 4}  # inputs
        assert call_args[2] == "call"  # event_type

        # Check second call (function completion)
        # For the result, we need to check the kwargs (index [1]), not positional args
        completion_call = mock_dispatch.call_args_list[1]
        completion_args = completion_call[0]  # positional args
        completion_kwargs = completion_call[1]  # keyword args

        assert completion_args[0] == "test_sync"  # func_name
        assert completion_args[2] == "completion"  # event_type
        assert completion_kwargs["result"] == 7  # result is a keyword arg

    @patch("uipath_langchain.tracers._instrument_traceable.dispatch_trace_event")
    def test_sync_wrapper_with_processors(self, mock_dispatch):
        # Create a traced wrapper with input and output processors
        wrapped = _create_traced_wrapper(
            func=sample_sync_function,
            input_processor=sample_input_processor,  # Updated function name
            output_processor=sample_output_processor,  # Updated function name
        )

        # Call the wrapped function
        result = wrapped(3, 4)

        # Verify the result (should be unmodified)
        assert result == 7

        # Verify input was processed
        call_args = mock_dispatch.call_args_list[0][0]
        assert call_args[1].get("processed") is True

        # Verify output was processed - use kwargs
        completion_kwargs = mock_dispatch.call_args_list[1][1]
        assert completion_kwargs["result"] == "processed_7"  # processed result

    @pytest.mark.asyncio
    @patch("uipath_langchain.tracers._instrument_traceable.dispatch_trace_event")
    async def test_async_wrapper(self, mock_dispatch):
        # Create a traced wrapper for an async function
        wrapped = _create_traced_wrapper(
            func=sample_async_function, span_type="async_test"
        )

        # Call the wrapped function
        result = await wrapped(5, 6)

        # Verify the result
        assert result == 11

        # Verify dispatch_trace_event was called twice
        assert mock_dispatch.call_count == 2

        # Check metadata contains correct span_type - look in kwargs for metadata
        first_call_kwargs = mock_dispatch.call_args_list[0][1]
        assert first_call_kwargs.get("metadata", {}).get("span_type") == "async_test"

    @patch("uipath_langchain.tracers._instrument_traceable.dispatch_trace_event")
    def test_generator_wrapper(self, mock_dispatch):
        # Create a traced wrapper for a generator function
        wrapped = _create_traced_wrapper(
            func=sample_generator_function,
        )

        # Call the wrapped function and collect results
        results = list(wrapped([1, 2, 3]))

        # Verify the results
        assert results == [2, 4, 6]

        # Verify dispatch_trace_event was called twice
        assert mock_dispatch.call_count == 2

        # Check completion event includes all yielded results - use kwargs
        completion_kwargs = mock_dispatch.call_args_list[1][1]
        assert completion_kwargs["result"] == [2, 4, 6]  # all results

    @pytest.mark.asyncio
    @patch("uipath_langchain.tracers._instrument_traceable.dispatch_trace_event")
    async def test_async_generator_wrapper(self, mock_dispatch):
        # Create a traced wrapper for an async generator function
        wrapped = _create_traced_wrapper(
            func=sample_async_generator_function,
            output_processor=sample_output_processor,  # Updated function name
        )

        # Call the wrapped function and collect results
        results = []
        async for item in wrapped([1, 2, 3]):
            results.append(item)

        # Verify the results
        assert results == [2, 4, 6]

        # Verify dispatch_trace_event was called twice
        assert mock_dispatch.call_count == 2

        # Check completion event includes processed results - use kwargs
        completion_kwargs = mock_dispatch.call_args_list[1][1]
        assert completion_kwargs["result"] == [
            "processed_2",
            "processed_4",
            "processed_6",
        ]


class TestFormatArgsForTrace:
    def test_format_simple_args(self):
        def sample_func(a, b, c=3):
            pass

        signature = inspect.signature(sample_func)
        result = format_args_for_trace(signature, 1, 2)

        assert result == {"a": 1, "b": 2, "c": 3}

    def test_format_with_self(self):
        class SampleClass:
            def method(self, a, b):
                pass

        instance = SampleClass()
        signature = inspect.signature(instance.method)
        result = format_args_for_trace(signature, 1, 2)

        assert result == {"a": 1, "b": 2}

    def test_format_with_kwargs(self):
        def sample_func(a, **kwargs):
            pass

        signature = inspect.signature(sample_func)
        result = format_args_for_trace(signature, 1, b=2, c=3)

        assert result == {"a": 1, "b": 2, "c": 3}
