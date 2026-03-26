import inspect
import json

from uipath.core.tracing._utils import format_args_for_trace, format_args_for_trace_json


class TestSpanUtils:
    def test_format_args_for_trace(self):
        # Simple function signature
        def func1(a, b, c=3):
            pass

        sig = inspect.signature(func1)
        result = format_args_for_trace(sig, 1, 2)
        assert result == {"a": 1, "b": 2, "c": 3}

        # Test with kwargs
        result = format_args_for_trace(sig, 1, c=4, b=5)
        assert result == {"a": 1, "b": 5, "c": 4}

        # Function with self parameter
        class TestClass:
            def method(self, x, y):
                pass

        sig = inspect.signature(TestClass.method)
        result = format_args_for_trace(sig, TestClass(), 10, 20)
        assert result == {"x": 10, "y": 20}

        # Function with **kwargs
        def func2(a, **kwargs):
            pass

        sig = inspect.signature(func2)
        result = format_args_for_trace(sig, 1, b=2, c=3)
        assert result == {"a": 1, "b": 2, "c": 3}

    def test_format_args_for_trace_json(self):
        def sample_func(a, b=None):
            pass

        sig = inspect.signature(sample_func)

        # Test with simple args
        json_result = format_args_for_trace_json(sig, 1, b="test")
        parsed = json.loads(json_result)
        assert parsed == {"a": 1, "b": "test"}

        # Test with non-serializable object
        class NonSerializable:
            pass

        json_result = format_args_for_trace_json(sig, 1, b=NonSerializable())
        # Should not raise exception
        parsed = json.loads(json_result)
        assert parsed["a"] == 1
        assert "b" in parsed  # The value will be a string representation

    def test_format_args_for_trace_json_with_class_type(self):
        """Test format_args_for_trace_json with a function that takes a class type as parameter."""
        from pydantic import BaseModel

        # Define a mock OutputFormat class (similar to the example)
        class OutputFormat(BaseModel):
            format_type: str = "json"
            strict: bool = True

        # Define a function that takes a class type parameter
        def chat_completions(messages, response_format=None):
            pass

        sig = inspect.signature(chat_completions)

        # Test with class type as parameter (not instance)
        json_result = format_args_for_trace_json(
            sig, [("human", "repeat this: hi!")], response_format=OutputFormat
        )

        # Should not raise exception and should serialize the class
        parsed = json.loads(json_result)
        # Note: tuples are serialized as lists in JSON
        assert parsed["messages"] == [["human", "repeat this: hi!"]]
        assert "response_format" in parsed

        # When a class type is passed, it should be serialized with class info
        response_format_data = parsed["response_format"]
        assert "__class__" in response_format_data
        assert response_format_data["__class__"] == "OutputFormat"
        assert "__module__" in response_format_data
        assert "schema" in response_format_data
