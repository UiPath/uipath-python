"""Tests for CacheManager."""

import tempfile
from pathlib import Path

import pytest

from uipath._cli._evals.mocks.cache_manager import CacheManager
from uipath._cli._evals.mocks.mocks import cache_manager_context


@pytest.fixture
def cache_manager():
    """Create a cache manager with a temp directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        cm = CacheManager(cache_dir=Path(tmpdir))
        cache_manager_context.set(cm)
        yield cm
        cache_manager_context.set(None)


def test_set_and_get_llm_mocker(cache_manager):
    """Test setting and getting a cached response for LLM mocker."""
    cache_key_data = {
        "prompt_generation_args": {
            "input": "test input",
        },
        "response_format": {"type": "json"},
        "completion_kwargs": {"temperature": 0.7},
    }

    response = {"result": "test response"}

    cache_manager.set(
        mocker_type="llm_mocker",
        cache_key_data=cache_key_data,
        response=response,
        function_name="test_function",
    )

    cached_response = cache_manager.get(
        mocker_type="llm_mocker",
        cache_key_data=cache_key_data,
        function_name="test_function",
    )

    assert cached_response == response


def test_set_and_get_input_mocker(cache_manager):
    """Test setting and getting a cached response for input mocker."""
    cache_key_data = {
        "prompt_generation_args": {
            "input": "test input",
        },
        "response_format": {"type": "json"},
        "completion_kwargs": {"temperature": 0.7},
    }

    response = {"input": "test input"}

    cache_manager.set(
        mocker_type="input_mocker",
        cache_key_data=cache_key_data,
        response=response,
        function_name="generate_llm_input",
    )

    cached_response = cache_manager.get(
        mocker_type="input_mocker",
        cache_key_data=cache_key_data,
        function_name="generate_llm_input",
    )

    assert cached_response == response


def test_cache_invalidation_on_prompt_args_change(cache_manager):
    """Test that changing the prompt generation args invalidates the cache."""
    cache_key_data1 = {
        "prompt_generation_args": {
            "input": "original input",
        },
        "response_format": {"type": "json"},
        "completion_kwargs": {"temperature": 0.7},
    }

    cache_key_data2 = {
        "prompt_generation_args": {
            "input": "modified input",
        },
        "response_format": {"type": "json"},
        "completion_kwargs": {"temperature": 0.7},
    }

    response1 = {"result": "response 1"}
    response2 = {"result": "response 2"}

    cache_manager.set(
        mocker_type="llm_mocker",
        cache_key_data=cache_key_data1,
        response=response1,
        function_name="test_function",
    )

    cache_manager.set(
        mocker_type="llm_mocker",
        cache_key_data=cache_key_data2,
        response=response2,
        function_name="test_function",
    )

    cached1 = cache_manager.get(
        mocker_type="llm_mocker",
        cache_key_data=cache_key_data1,
        function_name="test_function",
    )

    cached2 = cache_manager.get(
        mocker_type="llm_mocker",
        cache_key_data=cache_key_data2,
        function_name="test_function",
    )

    assert cached1 == response1
    assert cached2 == response2


def test_cache_invalidation_on_model_settings_change(cache_manager):
    """Test that changing model settings invalidates the cache."""
    cache_key_data1 = {
        "prompt_generation_args": {
            "input": "test input",
        },
        "response_format": {"type": "json"},
        "completion_kwargs": {"temperature": 0.7},
    }

    cache_key_data2 = {
        "prompt_generation_args": {
            "input": "test input",
        },
        "response_format": {"type": "json"},
        "completion_kwargs": {"temperature": 0.9},
    }

    response = {"result": "test response"}

    cache_manager.set(
        mocker_type="llm_mocker",
        cache_key_data=cache_key_data1,
        response=response,
        function_name="test_function",
    )

    cached_response = cache_manager.get(
        mocker_type="llm_mocker",
        cache_key_data=cache_key_data2,
        function_name="test_function",
    )

    assert cached_response is None
