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
