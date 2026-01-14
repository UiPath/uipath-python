"""Tests for eval utility functions (input overrides)."""

from typing import Any

import pytest

from uipath._cli._evals._eval_util import apply_input_overrides, deep_merge


@pytest.mark.asyncio
async def test_input_override_simple_direct_field():
    """Test input override with simple direct field override."""
    # Set input overrides - per-evaluation format
    overrides = {
        "eval-1": {
            "a": 10,
            "operator": "*",
        }
    }

    # Test inputs
    inputs = {
        "a": 5,
        "b": 3,
        "operator": "+",
    }

    result = apply_input_overrides(inputs, overrides, eval_id="eval-1")

    assert result["a"] == 10  # Overridden
    assert result["operator"] == "*"  # Overridden
    assert result["b"] == 3  # Unchanged


@pytest.mark.asyncio
async def test_input_override_deep_merge():
    """Test input override with deep merge for nested objects."""
    overrides = {"eval-1": {"filePath": {"ID": "new-id-123", "NewField": "added"}}}

    inputs = {
        "filePath": {
            "ID": "old-id",
            "FullName": "test.pdf",
            "MimeType": "application/pdf",
        },
        "other": "value",
    }

    result = apply_input_overrides(inputs, overrides, eval_id="eval-1")

    # Deep merge: overridden fields updated, existing fields preserved
    assert result["filePath"]["ID"] == "new-id-123"  # Overridden
    assert result["filePath"]["NewField"] == "added"  # Added
    assert result["filePath"]["FullName"] == "test.pdf"  # Preserved
    assert result["filePath"]["MimeType"] == "application/pdf"  # Preserved
    assert result["other"] == "value"  # Unchanged


@pytest.mark.asyncio
async def test_input_override_no_overrides():
    """Test input override when no overrides are configured."""
    inputs = {"file_id": "attachment-123", "data": {"nested": "value"}}

    result = apply_input_overrides(inputs, {}, eval_id="eval-1")

    # Should return the same inputs unchanged
    assert result == inputs


@pytest.mark.asyncio
async def test_input_override_new_fields():
    """Test input override adding new fields."""
    overrides = {
        "eval-1": {
            "newField": "new-value",
            "c": 7,
        }
    }

    inputs = {"a": 5, "b": 3}

    result = apply_input_overrides(inputs, overrides, eval_id="eval-1")

    # New fields should be added
    assert result["a"] == 5  # Unchanged
    assert result["b"] == 3  # Unchanged
    assert result["newField"] == "new-value"  # Added
    assert result["c"] == 7  # Added


@pytest.mark.asyncio
async def test_input_override_multimodal():
    """Test input override with multimodal inputs (images, files)."""
    # Override image attachment ID using per-evaluation format
    overrides = {
        "eval-1": {
            "image": "job-attachment-xyz789",
            "filePath": {"ID": "document-id-current"},
        }
    }

    # Simulate a multimodal evaluation input with image and file references
    inputs = {
        "prompt": "Analyze this screenshot",
        "image": "job-attachment-abc123",
        "filePath": {
            "ID": "document-id-legacy",
            "FullName": "doc.pdf",
            "MimeType": "application/pdf",
        },
    }

    result = apply_input_overrides(inputs, overrides, eval_id="eval-1")

    # Verify overrides
    assert result["prompt"] == "Analyze this screenshot"  # Text unchanged
    assert result["image"] == "job-attachment-xyz789"  # Overridden
    assert result["filePath"]["ID"] == "document-id-current"  # Overridden
    assert result["filePath"]["FullName"] == "doc.pdf"  # Preserved
    assert result["filePath"]["MimeType"] == "application/pdf"  # Preserved


@pytest.mark.asyncio
async def test_input_override_calculator_example():
    """Test input override with calculator-style inputs."""
    # Override calculator inputs using per-evaluation format
    overrides = {
        "eval-1": {
            "a": 10,
            "operator": "*",
        }
    }

    inputs = {"a": 5, "b": 3, "operator": "+"}

    result = apply_input_overrides(inputs, overrides, eval_id="eval-1")

    # Direct field override
    assert result["a"] == 10  # Overridden
    assert result["operator"] == "*"  # Overridden
    assert result["b"] == 3  # Unchanged


@pytest.mark.asyncio
async def test_deep_merge_multiple_levels():
    """Test deep merge with multiple levels of nesting."""
    overrides = {
        "eval-1": {
            "config": {
                "database": {
                    "connection": {
                        "host": "new-host",
                        "timeout": 5000,
                    }
                }
            }
        }
    }

    inputs = {
        "config": {
            "database": {
                "connection": {
                    "host": "localhost",
                    "port": 5432,
                    "ssl": True,
                },
                "pool_size": 10,
            },
            "logging": {"level": "INFO"},
        }
    }

    result = apply_input_overrides(inputs, overrides, eval_id="eval-1")

    # Verify deep merge at multiple levels
    assert (
        result["config"]["database"]["connection"]["host"] == "new-host"
    )  # Overridden
    assert result["config"]["database"]["connection"]["timeout"] == 5000  # Added
    assert result["config"]["database"]["connection"]["port"] == 5432  # Preserved
    assert result["config"]["database"]["connection"]["ssl"] is True  # Preserved
    assert result["config"]["database"]["pool_size"] == 10  # Preserved
    assert result["config"]["logging"]["level"] == "INFO"  # Preserved


@pytest.mark.asyncio
async def test_deep_merge_replace_dict_with_primitive():
    """Test deep merge when replacing a dict value with a primitive."""
    overrides = {
        "eval-1": {
            "config": "simple-string",  # Replace entire dict with string
        }
    }

    inputs = {
        "config": {
            "database": "postgres",
            "port": 5432,
        },
        "other": "value",
    }

    result = apply_input_overrides(inputs, overrides, eval_id="eval-1")

    # Dict should be replaced with primitive
    assert result["config"] == "simple-string"  # Completely replaced
    assert result["other"] == "value"  # Unchanged


@pytest.mark.asyncio
async def test_deep_merge_replace_primitive_with_dict():
    """Test deep merge when replacing a primitive value with a dict."""
    overrides = {
        "eval-1": {
            "setting": {
                "enabled": True,
                "mode": "advanced",
            }
        }
    }

    inputs = {
        "setting": "default",
        "other": "value",
    }

    result = apply_input_overrides(inputs, overrides, eval_id="eval-1")

    # Primitive should be replaced with dict
    assert isinstance(result["setting"], dict)
    assert result["setting"]["enabled"] is True
    assert result["setting"]["mode"] == "advanced"
    assert result["other"] == "value"  # Unchanged


@pytest.mark.asyncio
async def test_deep_merge_empty_dict():
    """Test deep merge with empty dictionaries."""
    overrides = {
        "eval-1": {
            "empty": {},
            "populated": {"key": "value"},
        }
    }

    inputs = {
        "empty": {"existing": "data"},
        "populated": {},
    }

    result = apply_input_overrides(inputs, overrides, eval_id="eval-1")

    # Empty dict override should preserve existing fields
    assert result["empty"]["existing"] == "data"
    # Override with populated dict should add fields to empty base
    assert result["populated"]["key"] == "value"


@pytest.mark.asyncio
async def test_deep_merge_list_values():
    """Test deep merge with list values (should replace, not merge)."""
    overrides = {
        "eval-1": {
            "tags": ["new", "tags"],
            "nested": {"items": [3, 4, 5]},
        }
    }

    inputs = {
        "tags": ["old", "values"],
        "nested": {"items": [1, 2], "other": "value"},
    }

    result = apply_input_overrides(inputs, overrides, eval_id="eval-1")

    # Lists should be replaced entirely, not merged
    assert result["tags"] == ["new", "tags"]
    assert result["nested"]["items"] == [3, 4, 5]
    assert result["nested"]["other"] == "value"  # Other keys preserved


@pytest.mark.asyncio
async def test_deep_merge_complex_nested_structure():
    """Test deep merge with a complex nested structure."""
    overrides = {
        "eval-1": {
            "api": {
                "endpoints": {
                    "auth": {
                        "url": "https://new-auth.api.com",
                        "timeout": 3000,
                    }
                }
            }
        }
    }

    inputs = {
        "api": {
            "version": "v2",
            "endpoints": {
                "auth": {
                    "url": "https://old-auth.api.com",
                    "method": "POST",
                    "retries": 3,
                },
                "data": {
                    "url": "https://data.api.com",
                },
            },
            "headers": {"Authorization": "Bearer token"},
        }
    }

    result = apply_input_overrides(inputs, overrides, eval_id="eval-1")

    # Verify deep merge preserves structure
    assert result["api"]["version"] == "v2"  # Top-level preserved
    assert (
        result["api"]["endpoints"]["auth"]["url"] == "https://new-auth.api.com"
    )  # Overridden
    assert result["api"]["endpoints"]["auth"]["timeout"] == 3000  # Added
    assert result["api"]["endpoints"]["auth"]["method"] == "POST"  # Preserved
    assert result["api"]["endpoints"]["auth"]["retries"] == 3  # Preserved
    assert (
        result["api"]["endpoints"]["data"]["url"] == "https://data.api.com"
    )  # Sibling preserved
    assert (
        result["api"]["headers"]["Authorization"] == "Bearer token"
    )  # Sibling preserved


@pytest.mark.asyncio
async def test_deep_merge_none_values():
    """Test deep merge with None values."""
    overrides = {
        "eval-1": {
            "nullable": None,
            "nested": {"field": None},
        }
    }

    inputs = {
        "nullable": "original-value",
        "nested": {"field": "original", "other": "preserved"},
    }

    result = apply_input_overrides(inputs, overrides, eval_id="eval-1")

    # None values should override existing values
    assert result["nullable"] is None
    assert result["nested"]["field"] is None
    assert result["nested"]["other"] == "preserved"


@pytest.mark.asyncio
async def test_deep_merge_numeric_and_boolean_types():
    """Test deep merge with various primitive types."""
    overrides = {
        "eval-1": {
            "count": 100,
            "ratio": 0.75,
            "enabled": False,
            "config": {
                "max_retries": 5,
                "timeout": 30.5,
                "debug": True,
            },
        }
    }

    inputs = {
        "count": 10,
        "ratio": 0.5,
        "enabled": True,
        "config": {
            "max_retries": 3,
            "timeout": 10.0,
            "debug": False,
            "log_level": "INFO",
        },
    }

    result = apply_input_overrides(inputs, overrides, eval_id="eval-1")

    # Verify all primitive types are handled correctly
    assert result["count"] == 100
    assert result["ratio"] == 0.75
    assert result["enabled"] is False
    assert result["config"]["max_retries"] == 5
    assert result["config"]["timeout"] == 30.5
    assert result["config"]["debug"] is True
    assert result["config"]["log_level"] == "INFO"  # Preserved


@pytest.mark.asyncio
async def test_deep_merge_does_not_mutate_original():
    """Test that deep merge does not mutate the original inputs."""
    overrides = {"eval-1": {"nested": {"field": "new-value"}}}

    original_inputs: dict[str, Any] = {
        "nested": {"field": "original", "other": "data"},
        "top": "level",
    }

    # Create a deep copy to compare later
    import copy

    inputs_before = copy.deepcopy(original_inputs)

    result = apply_input_overrides(original_inputs, overrides, eval_id="eval-1")

    # Verify result has overrides
    assert result["nested"]["field"] == "new-value"

    # Verify original inputs are unchanged
    assert original_inputs == inputs_before
    assert original_inputs["nested"]["field"] == "original"


@pytest.mark.asyncio
async def test_deep_merge_function_directly():
    """Test deep_merge function directly."""
    base = {
        "a": 1,
        "b": {"c": 2, "d": 3},
        "e": "unchanged",
    }

    override = {
        "b": {"c": 10},  # Override nested value
        "f": "new",  # Add new key
    }

    result = deep_merge(base, override)

    assert result["a"] == 1  # Preserved
    assert result["b"]["c"] == 10  # Overridden
    assert result["b"]["d"] == 3  # Preserved
    assert result["e"] == "unchanged"  # Preserved
    assert result["f"] == "new"  # Added


@pytest.mark.asyncio
async def test_input_override_no_eval_id():
    """Test input override when eval_id is not provided."""
    overrides = {"eval-1": {"a": 10}}
    inputs = {"a": 5, "b": 3}

    result = apply_input_overrides(inputs, overrides, eval_id=None)

    # Should return original inputs unchanged
    assert result == inputs


@pytest.mark.asyncio
async def test_input_override_nonexistent_eval_id():
    """Test input override when eval_id doesn't have overrides."""
    overrides = {"eval-1": {"a": 10}}
    inputs = {"a": 5, "b": 3}

    result = apply_input_overrides(inputs, overrides, eval_id="eval-2")

    # Should return original inputs unchanged
    assert result == inputs
