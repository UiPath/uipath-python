"""Unit tests for TYPE_REGISTRY module.

Tests cover:
- get_type() basic functionality
- get_type() error handling
- register_type() custom type registration
- is_valid_type() validation
- Security: ensuring eval() is not used
"""

import pytest

from uipath._cli._utils._type_registry import (
    TYPE_REGISTRY,
    get_type,
    is_valid_type,
    register_type,
)


class TestGetType:
    """Test get_type() function."""

    def test_get_type_str(self):
        """Test getting str type."""
        result = get_type("str")
        assert result is str

    def test_get_type_int(self):
        """Test getting int type."""
        result = get_type("int")
        assert result is int

    def test_get_type_bool(self):
        """Test getting bool type."""
        result = get_type("bool")
        assert result is bool

    def test_get_type_float(self):
        """Test getting float type."""
        result = get_type("float")
        assert result is float

    def test_get_type_invalid_raises_value_error(self):
        """Test that invalid type name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            get_type("InvalidType")

        error_msg = str(exc_info.value)
        assert "Unknown type: 'InvalidType'" in error_msg
        assert "Valid types:" in error_msg
        assert "str" in error_msg
        assert "int" in error_msg

    def test_get_type_case_sensitive(self):
        """Test that type names are case-sensitive."""
        with pytest.raises(ValueError):
            get_type("STR")  # Should be "str"

        with pytest.raises(ValueError):
            get_type("Int")  # Should be "int"


class TestIsValidType:
    """Test is_valid_type() function."""

    def test_is_valid_type_str(self):
        """Test that 'str' is valid."""
        assert is_valid_type("str") is True

    def test_is_valid_type_int(self):
        """Test that 'int' is valid."""
        assert is_valid_type("int") is True

    def test_is_valid_type_bool(self):
        """Test that 'bool' is valid."""
        assert is_valid_type("bool") is True

    def test_is_valid_type_float(self):
        """Test that 'float' is valid."""
        assert is_valid_type("float") is True

    def test_is_valid_type_invalid(self):
        """Test that invalid type returns False."""
        assert is_valid_type("InvalidType") is False
        assert is_valid_type("list") is False  # Not registered
        assert is_valid_type("dict") is False  # Not registered

    def test_is_valid_type_empty_string(self):
        """Test that empty string is invalid."""
        assert is_valid_type("") is False


class TestRegisterType:
    """Test register_type() function."""

    def test_register_type_custom(self):
        """Test registering a custom type."""
        from pathlib import Path

        # Clean up if already registered (from previous test run)
        if "path" in TYPE_REGISTRY:
            del TYPE_REGISTRY["path"]

        register_type("path", Path)

        # Verify it's registered
        assert is_valid_type("path")
        assert get_type("path") is Path

        # Clean up
        del TYPE_REGISTRY["path"]

    def test_register_type_duplicate_raises(self):
        """Test that registering duplicate type raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            register_type("str", str)  # str is already registered

        error_msg = str(exc_info.value)
        assert "str" in error_msg
        assert "already registered" in error_msg

    def test_register_type_persists(self):
        """Test that registered type persists."""
        # Clean up if exists
        if "custom_type" in TYPE_REGISTRY:
            del TYPE_REGISTRY["custom_type"]

        class CustomType:
            pass

        register_type("custom_type", CustomType)

        # Verify persistence
        assert is_valid_type("custom_type")
        assert get_type("custom_type") is CustomType

        # Clean up
        del TYPE_REGISTRY["custom_type"]


class TestTypeRegistrySecurity:
    """Test security aspects of TYPE_REGISTRY."""

    def test_type_registry_does_not_use_eval(self):
        """Test that get_type() does not use eval().

        This is a critical security test ensuring we don't execute
        arbitrary code via eval().
        """
        # Attempt to inject code via type name
        malicious_input = "__import__('os').system('echo pwned')"

        with pytest.raises(ValueError):
            get_type(malicious_input)

        # Verify the malicious code was not executed (would not be in registry)
        assert malicious_input not in TYPE_REGISTRY

    def test_type_registry_only_allows_registered_types(self):
        """Test that only explicitly registered types are allowed."""
        # These types exist in Python but are not in our registry
        unsafe_types = ["list", "dict", "tuple", "set", "object", "type"]

        for unsafe_type in unsafe_types:
            assert not is_valid_type(unsafe_type), (
                f"Type '{unsafe_type}' should not be valid"
            )

            with pytest.raises(ValueError):
                get_type(unsafe_type)


class TestTypeRegistryDefaults:
    """Test default registered types."""

    def test_type_registry_has_expected_defaults(self):
        """Test that TYPE_REGISTRY has all expected default types."""
        expected_types = {"str", "int", "bool", "float"}
        actual_types = set(TYPE_REGISTRY.keys())

        # Check that at least the expected types are present
        # (there might be more if custom types were registered)
        assert expected_types.issubset(actual_types), (
            f"Missing expected types: {expected_types - actual_types}"
        )

    def test_type_registry_str_maps_to_str_class(self):
        """Test that 'str' maps to actual str class."""
        assert TYPE_REGISTRY["str"] is str

    def test_type_registry_int_maps_to_int_class(self):
        """Test that 'int' maps to actual int class."""
        assert TYPE_REGISTRY["int"] is int

    def test_type_registry_bool_maps_to_bool_class(self):
        """Test that 'bool' maps to actual bool class."""
        assert TYPE_REGISTRY["bool"] is bool

    def test_type_registry_float_maps_to_float_class(self):
        """Test that 'float' maps to actual float class."""
        assert TYPE_REGISTRY["float"] is float
