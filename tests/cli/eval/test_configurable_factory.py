"""Tests for ConfigurableRuntimeFactory."""

import json
import tempfile
from pathlib import Path
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
