"""Tests for CacheManager."""

import tempfile
from pathlib import Path

import pytest

from uipath._cli._evals.mocks.cache_manager import CacheManager


@pytest.fixture(autouse=True)
def temp_cache_dir(monkeypatch):
    """Override cache directory to use temp directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(CacheManager, "_CACHE_DIR", Path(tmpdir))
        yield Path(tmpdir)


def test_set_and_get_llm_mocker():
    """Test setting and getting a cached response for LLM mocker."""
    cache_key_data = {
        "prompt": "test prompt",
        "response_format": {"type": "json"},
        "completion_kwargs": {"temperature": 0.7},
    }

    response = {"result": "test response"}

    CacheManager.set(
        mocker_type="llm_mocker",
        eval_set_id="evalset-456",
        eval_item_id="eval-123",
        cache_key_data=cache_key_data,
        response=response,
        function_name="test_function",
    )

    cached_response = CacheManager.get(
        mocker_type="llm_mocker",
        eval_set_id="evalset-456",
        eval_item_id="eval-123",
        cache_key_data=cache_key_data,
        function_name="test_function",
    )

    assert cached_response == response


def test_set_and_get_input_mocker():
    """Test setting and getting a cached response for input mocker."""
    cache_key_data = {
        "prompt": "test prompt",
        "response_format": {"type": "json"},
        "completion_kwargs": {"temperature": 0.7},
    }

    response = {"input": "test input"}

    CacheManager.set(
        mocker_type="input_mocker",
        eval_set_id="evalset-789",
        eval_item_id="eval-456",
        cache_key_data=cache_key_data,
        response=response,
    )

    cached_response = CacheManager.get(
        mocker_type="input_mocker",
        eval_set_id="evalset-789",
        eval_item_id="eval-456",
        cache_key_data=cache_key_data,
    )

    assert cached_response == response


def test_cache_invalidation_on_prompt_change():
    """Test that changing the prompt invalidates the cache."""
    cache_key_data1 = {
        "prompt": "original prompt",
        "response_format": {"type": "json"},
        "completion_kwargs": {"temperature": 0.7},
    }

    cache_key_data2 = {
        "prompt": "modified prompt",
        "response_format": {"type": "json"},
        "completion_kwargs": {"temperature": 0.7},
    }

    response1 = {"result": "response 1"}
    response2 = {"result": "response 2"}

    CacheManager.set(
        mocker_type="llm_mocker",
        eval_set_id="evalset-456",
        eval_item_id="eval-123",
        cache_key_data=cache_key_data1,
        response=response1,
        function_name="test_function",
    )

    CacheManager.set(
        mocker_type="llm_mocker",
        eval_set_id="evalset-456",
        eval_item_id="eval-123",
        cache_key_data=cache_key_data2,
        response=response2,
        function_name="test_function",
    )

    cached1 = CacheManager.get(
        mocker_type="llm_mocker",
        eval_set_id="evalset-456",
        eval_item_id="eval-123",
        cache_key_data=cache_key_data1,
        function_name="test_function",
    )

    cached2 = CacheManager.get(
        mocker_type="llm_mocker",
        eval_set_id="evalset-456",
        eval_item_id="eval-123",
        cache_key_data=cache_key_data2,
        function_name="test_function",
    )

    assert cached1 == response1
    assert cached2 == response2


def test_cache_invalidation_on_model_settings_change():
    """Test that changing model settings invalidates the cache."""
    cache_key_data1 = {
        "prompt": "test prompt",
        "response_format": {"type": "json"},
        "completion_kwargs": {"temperature": 0.7},
    }

    cache_key_data2 = {
        "prompt": "test prompt",
        "response_format": {"type": "json"},
        "completion_kwargs": {"temperature": 0.9},
    }

    response = {"result": "test response"}

    CacheManager.set(
        mocker_type="llm_mocker",
        eval_set_id="evalset-456",
        eval_item_id="eval-123",
        cache_key_data=cache_key_data1,
        response=response,
        function_name="test_function",
    )

    cached_response = CacheManager.get(
        mocker_type="llm_mocker",
        eval_set_id="evalset-456",
        eval_item_id="eval-123",
        cache_key_data=cache_key_data2,
        function_name="test_function",
    )

    assert cached_response is None
