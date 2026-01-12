"""Tests for text_tokens.py utils."""

import pytest

from uipath.agent.models.agent import TextToken, TextTokenType
from uipath.agent.utils.text_tokens import (
    build_string_from_tokens,
    safe_get_nested,
    serialize_argument,
)


class TestBuildStringFromTokens:
    """Test building strings from text tokens."""

    def test_simple_text_tokens(self):
        """Test simple text tokens are joined correctly."""
        tokens = [
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string="Hello "),
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string="World"),
        ]
        result = build_string_from_tokens(tokens, {})
        assert result == "Hello World"

    def test_with_input_variable_replacement(self):
        """Test input.* variable tokens are replaced with input values."""
        tokens = [
            TextToken(
                type=TextTokenType.SIMPLE_TEXT,
                raw_string="What is the weather like in ",
            ),
            TextToken(type=TextTokenType.VARIABLE, raw_string="input.city"),
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string="?"),
        ]
        result = build_string_from_tokens(tokens, {"city": "London"})
        assert result == "What is the weather like in London?"

    def test_with_output_variable(self):
        """Test output.* variable tokens return the path."""
        tokens = [
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string="Put the results in "),
            TextToken(type=TextTokenType.VARIABLE, raw_string="output.weather"),
        ]
        result = build_string_from_tokens(tokens, {})
        assert result == "Put the results in weather"

    def test_spec_example_without_tool_names(self):
        """Test the spec example without tool names (tools.weather remains unresolved)."""
        tokens = [
            TextToken(
                type=TextTokenType.SIMPLE_TEXT,
                raw_string="What is the weather like in ",
            ),
            TextToken(type=TextTokenType.VARIABLE, raw_string="input.city"),
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string="?\nUse the "),
            TextToken(type=TextTokenType.VARIABLE, raw_string="tools.weather"),
            TextToken(
                type=TextTokenType.SIMPLE_TEXT,
                raw_string=" tool and put the results in ",
            ),
            TextToken(type=TextTokenType.VARIABLE, raw_string="output.weather"),
        ]
        result = build_string_from_tokens(tokens, {"city": "London"})
        # tools.weather is not resolved (returns raw string), output.weather returns "weather"
        assert (
            result
            == "What is the weather like in London?\nUse the tools.weather tool and put the results in weather"
        )

    def test_spec_example_with_tool_names(self):
        """Test the spec example with tool names resolves correctly."""
        tokens = [
            TextToken(
                type=TextTokenType.SIMPLE_TEXT,
                raw_string="What is the weather like in ",
            ),
            TextToken(type=TextTokenType.VARIABLE, raw_string="input.city"),
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string="?\nUse the "),
            TextToken(type=TextTokenType.VARIABLE, raw_string="tools.weather"),
            TextToken(
                type=TextTokenType.SIMPLE_TEXT,
                raw_string=" tool and put the results in ",
            ),
            TextToken(type=TextTokenType.VARIABLE, raw_string="output.weather"),
        ]
        result = build_string_from_tokens(
            tokens, {"city": "London"}, tool_names=["weather"]
        )
        assert (
            result
            == "What is the weather like in London?\nUse the weather tool and put the results in weather"
        )

    def test_with_nested_input_object(self):
        """Test nested input objects are replaced correctly."""
        tokens = [
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string="The person is "),
            TextToken(type=TextTokenType.VARIABLE, raw_string="input.person.age"),
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string=" years old"),
        ]
        result = build_string_from_tokens(
            tokens, {"person": {"age": 25, "name": "John"}}
        )
        assert result == "The person is 25 years old"

    def test_expression_token_copies_raw_string(self):
        """Test expression tokens are copied as-is."""
        tokens = [
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string="Result: "),
            TextToken(type=TextTokenType.EXPRESSION, raw_string="{{some.expression}}"),
        ]
        result = build_string_from_tokens(tokens, {})
        assert result == "Result: {{some.expression}}"

    def test_input_variable_returns_entire_input_as_json(self):
        """Test 'input' variable returns entire input as JSON."""
        tokens = [
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string="Input: "),
            TextToken(type=TextTokenType.VARIABLE, raw_string="input"),
        ]
        result = build_string_from_tokens(tokens, {"city": "London", "temp": 20})
        assert result == 'Input: {"city": "London", "temp": 20}'

    @pytest.mark.parametrize(
        "raw_string,expected",
        [
            ("", ""),
            ("   ", "   "),
            ("unknown", "unknown"),
            ("unknown.path", "unknown.path"),
        ],
    )
    def test_unknown_variable_patterns_return_raw_string(self, raw_string, expected):
        """Test unknown variable patterns return the raw string."""
        tokens = [TextToken(type=TextTokenType.VARIABLE, raw_string=raw_string)]
        result = build_string_from_tokens(tokens, {"some": "value"})
        assert result == expected

    def test_missing_input_value_returns_raw_string(self):
        """Test missing input values return the raw variable string."""
        tokens = [
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string="Value: "),
            TextToken(type=TextTokenType.VARIABLE, raw_string="input.missing"),
        ]
        result = build_string_from_tokens(tokens, {"other": "value"})
        assert result == "Value: input.missing"

    def test_tool_reference_resolves_to_tool_name(self):
        """Test tools.* variable resolves to tool name."""
        tokens = [
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string="Use the "),
            TextToken(type=TextTokenType.VARIABLE, raw_string="tools.weather"),
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string=" tool"),
        ]
        result = build_string_from_tokens(
            tokens, {}, tool_names=["weather", "calculator"]
        )
        assert result == "Use the weather tool"

    def test_tool_reference_case_insensitive(self):
        """Test tools.* variable resolution is case-insensitive."""
        tokens = [
            TextToken(type=TextTokenType.VARIABLE, raw_string="tools.WEATHER"),
        ]
        result = build_string_from_tokens(tokens, {}, tool_names=["weather"])
        assert result == "weather"

    def test_tool_reference_not_found_returns_raw_string(self):
        """Test unknown tool reference returns raw string."""
        tokens = [
            TextToken(type=TextTokenType.VARIABLE, raw_string="tools.unknown"),
        ]
        result = build_string_from_tokens(tokens, {}, tool_names=["weather"])
        assert result == "tools.unknown"

    def test_escalation_reference_resolves_to_escalation_name(self):
        """Test escalations.* variable resolves to escalation name."""
        tokens = [
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string="Escalate to "),
            TextToken(type=TextTokenType.VARIABLE, raw_string="escalations.support"),
        ]
        result = build_string_from_tokens(tokens, {}, escalation_names=["support"])
        assert result == "Escalate to support"

    def test_context_reference_resolves_to_context_name(self):
        """Test contexts.* variable resolves to context name."""
        tokens = [
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string="Search in "),
            TextToken(type=TextTokenType.VARIABLE, raw_string="contexts.docs"),
        ]
        result = build_string_from_tokens(tokens, {}, context_names=["docs"])
        assert result == "Search in docs"

    def test_multiple_resource_types_together(self):
        """Test using multiple resource types in one prompt."""
        tokens = [
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string="Use "),
            TextToken(type=TextTokenType.VARIABLE, raw_string="tools.weather"),
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string=" with "),
            TextToken(type=TextTokenType.VARIABLE, raw_string="contexts.docs"),
            TextToken(type=TextTokenType.SIMPLE_TEXT, raw_string=" or escalate to "),
            TextToken(type=TextTokenType.VARIABLE, raw_string="escalations.support"),
        ]
        result = build_string_from_tokens(
            tokens,
            {},
            tool_names=["weather"],
            escalation_names=["support"],
            context_names=["docs"],
        )
        assert result == "Use weather with docs or escalate to support"


class TestSafeGetNested:
    """Test nested dictionary access."""

    def test_simple_key(self):
        """Test accessing simple top-level key."""
        data = {"name": "Alice"}
        assert safe_get_nested(data, "name") == "Alice"

    def test_nested_key(self):
        """Test accessing nested keys with dot notation."""
        data = {"user": {"name": "Alice", "age": 30}}
        assert safe_get_nested(data, "user.name") == "Alice"
        assert safe_get_nested(data, "user.age") == 30

    def test_missing_key(self):
        """Test accessing missing keys returns None."""
        data = {"user": {"name": "Alice"}}
        assert safe_get_nested(data, "user.missing") is None
        assert safe_get_nested(data, "missing.key") is None

    def test_array_value(self):
        """Test accessing array values."""
        data = {"items": [1, 2, 3]}
        assert safe_get_nested(data, "items") == [1, 2, 3]

    def test_deeply_nested(self):
        """Test deeply nested access."""
        data = {"level1": {"level2": {"level3": {"value": "deep"}}}}
        assert safe_get_nested(data, "level1.level2.level3.value") == "deep"

    def test_null_intermediate_value(self):
        """Test access through null intermediate value."""
        data = {"user": None}
        assert safe_get_nested(data, "user.name") is None


class TestSerializeValue:
    """Test value serialization."""

    def test_string(self):
        """Test serializing strings."""
        assert serialize_argument("hello") == "hello"

    def test_number(self):
        """Test serializing numbers."""
        assert serialize_argument(42) == "42"
        assert serialize_argument(3.14) == "3.14"

    def test_list(self):
        """Test serializing lists."""
        assert serialize_argument([1, 2, 3]) == "[1, 2, 3]"

    def test_dict(self):
        """Test serializing dictionaries."""
        result = serialize_argument({"key": "value"})
        assert '"key"' in result
        assert '"value"' in result

    def test_none(self):
        """Test serializing None returns empty string."""
        assert serialize_argument(None) == ""

    def test_boolean(self):
        """Test serializing booleans (JSON-style lowercase)."""
        assert serialize_argument(True) == "true"
        assert serialize_argument(False) == "false"
