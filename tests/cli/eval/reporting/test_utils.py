"""Tests for evaluation reporting utilities.

This module tests utility functions and decorators including:
- gracefully_handle_errors decorator
"""

from unittest.mock import Mock

import pytest

from uipath._cli._evals._reporting._utils import gracefully_handle_errors


class TestGracefullyHandleErrors:
    """Tests for the gracefully_handle_errors decorator."""

    @pytest.mark.asyncio
    async def test_successful_execution(self):
        """Test that successful functions return normally."""

        class TestClass:
            _console = Mock()

            @gracefully_handle_errors
            async def test_method(self, value):
                return value * 2

        obj = TestClass()
        result = await obj.test_method(5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_exception_returns_none(self):
        """Test that exceptions are caught and None is returned."""

        class TestClass:
            _console = Mock()

            @gracefully_handle_errors
            async def test_method(self):
                raise ValueError("Test error")

        obj = TestClass()
        result = await obj.test_method()
        assert result is None

    @pytest.mark.asyncio
    async def test_exception_without_console(self):
        """Test that exceptions are handled even without _console attribute."""

        class TestClass:
            @gracefully_handle_errors
            async def test_method(self):
                raise RuntimeError("Test error")

        obj = TestClass()
        result = await obj.test_method()
        assert result is None

    @pytest.mark.asyncio
    async def test_preserves_function_metadata(self):
        """Test that the decorator preserves function metadata."""

        class TestClass:
            _console = Mock()

            @gracefully_handle_errors
            async def documented_method(self):
                """This is a documented method."""
                return "success"

        obj = TestClass()
        assert obj.documented_method.__name__ == "documented_method"
        assert "documented" in obj.documented_method.__doc__

    @pytest.mark.asyncio
    async def test_handles_multiple_args_and_kwargs(self):
        """Test that the decorator handles multiple arguments correctly."""

        class TestClass:
            _console = Mock()

            @gracefully_handle_errors
            async def test_method(self, a, b, c=None, d=None):
                return a + b + (c or 0) + (d or 0)

        obj = TestClass()
        result = await obj.test_method(1, 2, c=3, d=4)
        assert result == 10
