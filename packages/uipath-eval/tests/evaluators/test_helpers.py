"""Test module for helper functions in uipath.eval._helpers.helpers."""

from uipath.eval._helpers.helpers import is_empty_value


class TestIsEmptyValue:
    """Test is_empty_value helper function.

    These tests are based on realistic evaluation criteria structures:
    - expectedOutput: typically a dict like {"content": "..."} or empty dict {}
    - expectedAgentBehavior: typically a string describing expected behavior
    """

    # --- Empty expectedAgentBehavior (string) cases ---

    def test_empty_string_expected_agent_behavior(self) -> None:
        """Test empty string expectedAgentBehavior is considered empty."""
        assert is_empty_value("") is True

    def test_whitespace_only_expected_agent_behavior(self) -> None:
        """Test whitespace-only expectedAgentBehavior is considered empty."""
        assert is_empty_value(" ") is True
        assert is_empty_value("   ") is True
        assert is_empty_value("\t") is True
        assert is_empty_value("\n") is True
        assert is_empty_value(" \t\n ") is True

    def test_valid_expected_agent_behavior(self) -> None:
        """Test non-empty expectedAgentBehavior strings are not empty."""
        assert is_empty_value("The agent should search for weather") is False
        assert is_empty_value("Call the get_user tool with id=123") is False
        assert is_empty_value(" valid behavior ") is False

    # --- Empty expectedOutput (dict) cases ---

    def test_empty_dict_expected_output(self) -> None:
        """Test empty dict expectedOutput is considered empty."""
        # trajectory evaluator: {"expectedOutput": {}}
        assert is_empty_value({}) is True

    def test_dict_with_empty_content_field(self) -> None:
        """Test dict with empty content field is considered empty."""
        # llm-as-a-judge: {"expectedOutput": {"content": ""}}
        assert is_empty_value({"content": ""}) is True

    def test_dict_with_whitespace_content_field(self) -> None:
        """Test dict with whitespace-only content field is considered empty."""
        assert is_empty_value({"content": "   "}) is True
        assert is_empty_value({"content": "\t\n"}) is True

    def test_dict_with_multiple_empty_string_fields(self) -> None:
        """Test dict where all values are empty strings is considered empty."""
        assert is_empty_value({"content": "", "reasoning": ""}) is True
        assert is_empty_value({"content": "  ", "reasoning": "\t"}) is True

    def test_dict_with_valid_content_field(self) -> None:
        """Test dict with non-empty content field is not empty."""
        assert is_empty_value({"content": "Expected response"}) is False
        assert is_empty_value({"content": "The answer is 42"}) is False

    def test_dict_with_mixed_empty_and_non_empty_fields(self) -> None:
        """Test dict with at least one non-empty value is not empty."""
        # If any value is non-empty, the whole dict is not empty
        assert is_empty_value({"content": "value", "reasoning": ""}) is False
        assert is_empty_value({"content": "", "reasoning": "some reason"}) is False

    # --- None case ---

    def test_none_is_empty(self) -> None:
        """Test that None is considered empty."""
        assert is_empty_value(None) is True

    # --- Empty list case ---

    def test_empty_list_is_empty(self) -> None:
        """Test that empty list is considered empty."""
        assert is_empty_value([]) is True

    def test_non_empty_list_is_not_empty(self) -> None:
        """Test that non-empty lists are not considered empty."""
        assert is_empty_value(["step1", "step2"]) is False
        assert is_empty_value([{"content": ""}]) is False

    # --- Edge cases with non-string dict values ---

    def test_dict_with_non_string_values_is_not_empty(self) -> None:
        """Test that dict with non-string values is not considered empty.

        The function only checks if all values are empty strings.
        Non-string values (int, bool, None, list, dict) make it non-empty.
        """
        assert is_empty_value({"content": 0}) is False
        assert is_empty_value({"content": False}) is False
        assert is_empty_value({"content": None}) is False
        assert is_empty_value({"content": []}) is False
        assert is_empty_value({"content": {}}) is False

    # --- Other types (not typical in eval criteria but handled) ---

    def test_numeric_values_are_not_empty(self) -> None:
        """Test that numeric values are not considered empty."""
        assert is_empty_value(0) is False
        assert is_empty_value(42) is False
        assert is_empty_value(0.0) is False

    def test_boolean_values_are_not_empty(self) -> None:
        """Test that boolean values are not considered empty."""
        assert is_empty_value(False) is False
        assert is_empty_value(True) is False
