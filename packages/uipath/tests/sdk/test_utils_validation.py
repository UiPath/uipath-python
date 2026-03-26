"""Tests for shared validation utilities."""

import pytest

from uipath._utils.validation import validate_pagination_params


class TestValidatePaginationParams:
    """Test shared pagination parameter validation."""

    def test_valid_parameters(self):
        """Test validation passes with valid parameters."""
        validate_pagination_params(skip=0, top=100)
        validate_pagination_params(skip=5000, top=500)
        validate_pagination_params(skip=10000, top=1000)

    def test_skip_negative(self):
        """Test error when skip is negative."""
        with pytest.raises(ValueError, match="skip must be >= 0"):
            validate_pagination_params(skip=-1, top=100)

    def test_skip_exceeds_maximum(self):
        """Test error when skip exceeds max_skip."""
        with pytest.raises(
            ValueError, match=r"skip must be <= 10000.*requested: 10001"
        ):
            validate_pagination_params(skip=10001, top=100)

    def test_top_below_minimum(self):
        """Test error when top is below 1."""
        with pytest.raises(ValueError, match="top must be >= 1"):
            validate_pagination_params(skip=0, top=0)

    def test_top_exceeds_maximum(self):
        """Test error when top exceeds max_top."""
        with pytest.raises(ValueError, match=r"top must be <= 1000.*requested: 1001"):
            validate_pagination_params(skip=0, top=1001)

    def test_custom_limits(self):
        """Test validation with custom max limits."""
        validate_pagination_params(skip=500, top=50, max_skip=500, max_top=50)

        with pytest.raises(ValueError):
            validate_pagination_params(skip=501, top=50, max_skip=500, max_top=50)

    def test_skip_at_boundary(self):
        """Test that skip at maximum is allowed."""
        validate_pagination_params(skip=10000, top=100)

    def test_top_at_boundary(self):
        """Test that top at maximum is allowed."""
        validate_pagination_params(skip=0, top=1000)

    def test_skip_zero_is_valid(self):
        """Test that skip=0 is valid."""
        validate_pagination_params(skip=0, top=100)

    def test_top_one_is_valid(self):
        """Test that top=1 is valid minimum."""
        validate_pagination_params(skip=0, top=1)
