"""Tests for ConfigurableRuntimeFactory."""

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from uipath._cli._evals._configurable_factory import ConfigurableRuntimeFactory
from uipath._cli._evals._models._evaluation_set import EvaluationSetModelSettings


@pytest.mark.asyncio
async def test_configurable_factory_no_override():
    """Test factory without any overrides."""
    mock_base_factory = AsyncMock()
    mock_runtime = Mock()
    mock_base_factory.new_runtime.return_value = mock_runtime

    factory = ConfigurableRuntimeFactory(mock_base_factory)

    result = await factory.new_runtime("test.json", "test-id")

    assert result == mock_runtime
    mock_base_factory.new_runtime.assert_called_once_with("test.json", "test-id")


@pytest.mark.asyncio
async def test_configurable_factory_with_model_override():
    """Test factory with model override."""
    # Create a temporary agent.json file
    test_agent = {"settings": {"model": "gpt-4", "temperature": 0.7}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(test_agent, f)
        temp_path = f.name

    try:
        mock_base_factory = AsyncMock()
        mock_runtime = Mock()
        mock_base_factory.new_runtime.return_value = mock_runtime

        factory = ConfigurableRuntimeFactory(mock_base_factory)

        # Set model override
        settings = EvaluationSetModelSettings(
            id="test-settings", model_name="gpt-3.5-turbo", temperature="same-as-agent"
        )
        factory.set_model_settings_override(settings)

        result = await factory.new_runtime(temp_path, "test-id")

        assert result == mock_runtime
        # Should have been called with a modified temp file
        call_args = mock_base_factory.new_runtime.call_args
        assert call_args[0][0] != temp_path  # Different path (temp file)
        assert call_args[0][1] == "test-id"

        # Verify the temp file has correct content
        with open(call_args[0][0]) as f:
            modified_data = json.load(f)
        assert modified_data["settings"]["model"] == "gpt-3.5-turbo"
        assert modified_data["settings"]["temperature"] == 0.7  # Unchanged

    finally:
        Path(temp_path).unlink(missing_ok=True)
        # Clean up temp files created by factory
        await factory.dispose()


@pytest.mark.asyncio
async def test_configurable_factory_same_as_agent():
    """Test factory when both settings are 'same-as-agent'."""
    # Create a temporary agent.json file
    test_agent = {"settings": {"model": "gpt-4", "temperature": 0.7}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(test_agent, f)
        temp_path = f.name

    try:
        mock_base_factory = AsyncMock()
        mock_runtime = Mock()
        mock_base_factory.new_runtime.return_value = mock_runtime

        factory = ConfigurableRuntimeFactory(mock_base_factory)

        # Set "same-as-agent" for both
        settings = EvaluationSetModelSettings(
            id="test-settings", model_name="same-as-agent", temperature="same-as-agent"
        )
        factory.set_model_settings_override(settings)

        result = await factory.new_runtime(temp_path, "test-id")

        assert result == mock_runtime
        # Should use original path (no override)
        mock_base_factory.new_runtime.assert_called_once_with(temp_path, "test-id")

    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_configurable_factory_temperature_override():
    """Test factory with temperature override."""
    # Create a temporary agent.json file
    test_agent = {"settings": {"model": "gpt-4", "temperature": 0.7}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(test_agent, f)
        temp_path = f.name

    try:
        mock_base_factory = AsyncMock()
        mock_runtime = Mock()
        mock_base_factory.new_runtime.return_value = mock_runtime

        factory = ConfigurableRuntimeFactory(mock_base_factory)

        # Set temperature override
        settings = EvaluationSetModelSettings(
            id="test-settings", model_name="same-as-agent", temperature=0.2
        )
        factory.set_model_settings_override(settings)

        result = await factory.new_runtime(temp_path, "test-id")

        assert result == mock_runtime
        # Should have been called with a modified temp file
        call_args = mock_base_factory.new_runtime.call_args
        assert call_args[0][0] != temp_path  # Different path (temp file)

        # Verify the temp file has correct content
        with open(call_args[0][0]) as f:
            modified_data = json.load(f)
        assert modified_data["settings"]["model"] == "gpt-4"  # Unchanged
        assert modified_data["settings"]["temperature"] == 0.2  # Changed

    finally:
        Path(temp_path).unlink(missing_ok=True)
        await factory.dispose()


@pytest.mark.asyncio
async def test_configurable_factory_cleanup():
    """Test that temporary files are cleaned up."""
    test_agent = {"settings": {"model": "gpt-4", "temperature": 0.7}}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(test_agent, f)
        temp_path = f.name

    try:
        mock_base_factory = AsyncMock()
        mock_runtime = Mock()
        mock_base_factory.new_runtime.return_value = mock_runtime

        factory = ConfigurableRuntimeFactory(mock_base_factory)

        settings = EvaluationSetModelSettings(
            id="test-settings", model_name="gpt-3.5-turbo", temperature=0.5
        )
        factory.set_model_settings_override(settings)

        await factory.new_runtime(temp_path, "test-id")

        # Get the temp file created
        call_args = mock_base_factory.new_runtime.call_args
        temp_file_created = call_args[0][0]

        # Temp file should exist
        assert Path(temp_file_created).exists()

        # Clean up
        await factory.dispose()

        # Temp file should be deleted
        assert not Path(temp_file_created).exists()

    finally:
        Path(temp_path).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_input_override_simple_direct_field():
    """Test input override with simple direct field override."""
    mock_base_factory = AsyncMock()
    factory = ConfigurableRuntimeFactory(mock_base_factory)

    # Set input overrides - per-evaluation format
    overrides = {
        "eval-1": {
            "a": 10,
            "operator": "*",
        }
    }
    factory.set_input_overrides(overrides)

    # Test inputs
    inputs = {
        "a": 5,
        "b": 3,
        "operator": "+",
    }

    result = factory.apply_input_overrides(inputs, eval_id="eval-1")

    assert result["a"] == 10  # Overridden
    assert result["operator"] == "*"  # Overridden
    assert result["b"] == 3  # Unchanged


@pytest.mark.asyncio
async def test_input_override_deep_merge():
    """Test input override with deep merge for nested objects."""
    mock_base_factory = AsyncMock()
    factory = ConfigurableRuntimeFactory(mock_base_factory)

    overrides = {"eval-1": {"filePath": {"ID": "new-id-123", "NewField": "added"}}}
    factory.set_input_overrides(overrides)

    inputs = {
        "filePath": {
            "ID": "old-id",
            "FullName": "test.pdf",
            "MimeType": "application/pdf",
        },
        "other": "value",
    }

    result = factory.apply_input_overrides(inputs, eval_id="eval-1")

    # Deep merge: overridden fields updated, existing fields preserved
    assert result["filePath"]["ID"] == "new-id-123"  # Overridden
    assert result["filePath"]["NewField"] == "added"  # Added
    assert result["filePath"]["FullName"] == "test.pdf"  # Preserved
    assert result["filePath"]["MimeType"] == "application/pdf"  # Preserved
    assert result["other"] == "value"  # Unchanged


@pytest.mark.asyncio
async def test_input_override_no_overrides():
    """Test input override when no overrides are configured."""
    mock_base_factory = AsyncMock()
    factory = ConfigurableRuntimeFactory(mock_base_factory)

    inputs = {"file_id": "attachment-123", "data": {"nested": "value"}}

    result = factory.apply_input_overrides(inputs)

    # Should return the same inputs unchanged
    assert result == inputs


@pytest.mark.asyncio
async def test_input_override_new_fields():
    """Test input override adding new fields."""
    mock_base_factory = AsyncMock()
    factory = ConfigurableRuntimeFactory(mock_base_factory)

    overrides = {
        "eval-1": {
            "newField": "new-value",
            "c": 7,
        }
    }
    factory.set_input_overrides(overrides)

    inputs = {"a": 5, "b": 3}

    result = factory.apply_input_overrides(inputs, eval_id="eval-1")

    # New fields should be added
    assert result["a"] == 5  # Unchanged
    assert result["b"] == 3  # Unchanged
    assert result["newField"] == "new-value"  # Added
    assert result["c"] == 7  # Added


@pytest.mark.asyncio
async def test_input_override_multimodal():
    """Test input override with multimodal inputs (images, files)."""
    mock_base_factory = AsyncMock()
    factory = ConfigurableRuntimeFactory(mock_base_factory)

    # Override image attachment ID using per-evaluation format
    overrides = {
        "eval-1": {
            "image": "job-attachment-xyz789",
            "filePath": {"ID": "document-id-current"},
        }
    }
    factory.set_input_overrides(overrides)

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

    result = factory.apply_input_overrides(inputs, eval_id="eval-1")

    # Verify overrides
    assert result["prompt"] == "Analyze this screenshot"  # Text unchanged
    assert result["image"] == "job-attachment-xyz789"  # Overridden
    assert result["filePath"]["ID"] == "document-id-current"  # Overridden
    assert result["filePath"]["FullName"] == "doc.pdf"  # Preserved
    assert result["filePath"]["MimeType"] == "application/pdf"  # Preserved


@pytest.mark.asyncio
async def test_input_override_calculator_example():
    """Test input override with calculator-style inputs."""
    mock_base_factory = AsyncMock()
    factory = ConfigurableRuntimeFactory(mock_base_factory)

    # Override calculator inputs using per-evaluation format
    overrides = {
        "eval-1": {
            "a": 10,
            "operator": "*",
        }
    }
    factory.set_input_overrides(overrides)

    inputs = {"a": 5, "b": 3, "operator": "+"}

    result = factory.apply_input_overrides(inputs, eval_id="eval-1")

    # Direct field override
    assert result["a"] == 10  # Overridden
    assert result["operator"] == "*"  # Overridden
    assert result["b"] == 3  # Unchanged


@pytest.mark.asyncio
async def test_deep_merge_multiple_levels():
    """Test deep merge with multiple levels of nesting."""
    mock_base_factory = AsyncMock()
    factory = ConfigurableRuntimeFactory(mock_base_factory)

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
    factory.set_input_overrides(overrides)

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

    result = factory.apply_input_overrides(inputs, eval_id="eval-1")

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
    mock_base_factory = AsyncMock()
    factory = ConfigurableRuntimeFactory(mock_base_factory)

    overrides = {
        "eval-1": {
            "config": "simple-string",  # Replace entire dict with string
        }
    }
    factory.set_input_overrides(overrides)

    inputs = {
        "config": {
            "database": "postgres",
            "port": 5432,
        },
        "other": "value",
    }

    result = factory.apply_input_overrides(inputs, eval_id="eval-1")

    # Dict should be replaced with primitive
    assert result["config"] == "simple-string"  # Completely replaced
    assert result["other"] == "value"  # Unchanged


@pytest.mark.asyncio
async def test_deep_merge_replace_primitive_with_dict():
    """Test deep merge when replacing a primitive value with a dict."""
    mock_base_factory = AsyncMock()
    factory = ConfigurableRuntimeFactory(mock_base_factory)

    overrides = {
        "eval-1": {
            "setting": {
                "enabled": True,
                "mode": "advanced",
            }
        }
    }
    factory.set_input_overrides(overrides)

    inputs = {
        "setting": "default",
        "other": "value",
    }

    result = factory.apply_input_overrides(inputs, eval_id="eval-1")

    # Primitive should be replaced with dict
    assert isinstance(result["setting"], dict)
    assert result["setting"]["enabled"] is True
    assert result["setting"]["mode"] == "advanced"
    assert result["other"] == "value"  # Unchanged


@pytest.mark.asyncio
async def test_deep_merge_empty_dict():
    """Test deep merge with empty dictionaries."""
    mock_base_factory = AsyncMock()
    factory = ConfigurableRuntimeFactory(mock_base_factory)

    overrides = {
        "eval-1": {
            "empty": {},
            "populated": {"key": "value"},
        }
    }
    factory.set_input_overrides(overrides)

    inputs = {
        "empty": {"existing": "data"},
        "populated": {},
    }

    result = factory.apply_input_overrides(inputs, eval_id="eval-1")

    # Empty dict override should preserve existing fields
    assert result["empty"]["existing"] == "data"
    # Override with populated dict should add fields to empty base
    assert result["populated"]["key"] == "value"


@pytest.mark.asyncio
async def test_deep_merge_list_values():
    """Test deep merge with list values (should replace, not merge)."""
    mock_base_factory = AsyncMock()
    factory = ConfigurableRuntimeFactory(mock_base_factory)

    overrides = {
        "eval-1": {
            "tags": ["new", "tags"],
            "nested": {"items": [3, 4, 5]},
        }
    }
    factory.set_input_overrides(overrides)

    inputs = {
        "tags": ["old", "values"],
        "nested": {"items": [1, 2], "other": "value"},
    }

    result = factory.apply_input_overrides(inputs, eval_id="eval-1")

    # Lists should be replaced entirely, not merged
    assert result["tags"] == ["new", "tags"]
    assert result["nested"]["items"] == [3, 4, 5]
    assert result["nested"]["other"] == "value"  # Other keys preserved


@pytest.mark.asyncio
async def test_deep_merge_complex_nested_structure():
    """Test deep merge with a complex nested structure."""
    mock_base_factory = AsyncMock()
    factory = ConfigurableRuntimeFactory(mock_base_factory)

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
    factory.set_input_overrides(overrides)

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

    result = factory.apply_input_overrides(inputs, eval_id="eval-1")

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
    mock_base_factory = AsyncMock()
    factory = ConfigurableRuntimeFactory(mock_base_factory)

    overrides = {
        "eval-1": {
            "nullable": None,
            "nested": {"field": None},
        }
    }
    factory.set_input_overrides(overrides)

    inputs = {
        "nullable": "original-value",
        "nested": {"field": "original", "other": "preserved"},
    }

    result = factory.apply_input_overrides(inputs, eval_id="eval-1")

    # None values should override existing values
    assert result["nullable"] is None
    assert result["nested"]["field"] is None
    assert result["nested"]["other"] == "preserved"


@pytest.mark.asyncio
async def test_deep_merge_numeric_and_boolean_types():
    """Test deep merge with various primitive types."""
    mock_base_factory = AsyncMock()
    factory = ConfigurableRuntimeFactory(mock_base_factory)

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
    factory.set_input_overrides(overrides)

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

    result = factory.apply_input_overrides(inputs, eval_id="eval-1")

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
    mock_base_factory = AsyncMock()
    factory = ConfigurableRuntimeFactory(mock_base_factory)

    overrides = {"eval-1": {"nested": {"field": "new-value"}}}
    factory.set_input_overrides(overrides)

    original_inputs: dict[str, Any] = {
        "nested": {"field": "original", "other": "data"},
        "top": "level",
    }

    # Create a deep copy to compare later
    import copy

    inputs_before = copy.deepcopy(original_inputs)

    result = factory.apply_input_overrides(original_inputs, eval_id="eval-1")

    # Verify result has overrides
    assert result["nested"]["field"] == "new-value"

    # Verify original inputs are unchanged
    assert original_inputs == inputs_before
    assert original_inputs["nested"]["field"] == "original"
