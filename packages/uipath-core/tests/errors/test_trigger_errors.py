"""Tests for UiPath trigger error classes."""

from uipath.core.errors import (
    ErrorCategory,
    UiPathFaultedTriggerError,
    UiPathPendingTriggerError,
)


class TestUiPathFaultedTriggerError:
    """Test UiPathFaultedTriggerError constructor and behavior."""

    def test_init_with_detail(self) -> None:
        """Test that category, message, and detail are stored and str includes both."""
        err = UiPathFaultedTriggerError(
            category=ErrorCategory.USER,
            message="Something failed",
            detail="missing input",
        )
        assert err.category == ErrorCategory.USER
        assert err.message == "Something failed"
        assert err.detail == "missing input"
        assert str(err) == "Something failed: missing input"

    def test_init_without_detail(self) -> None:
        """Test that detail defaults to empty string and str is just the message."""
        err = UiPathFaultedTriggerError(
            category=ErrorCategory.SYSTEM,
            message="Internal error",
        )
        assert err.category == ErrorCategory.SYSTEM
        assert err.message == "Internal error"
        assert err.detail == ""
        assert str(err) == "Internal error"

    def test_is_exception(self) -> None:
        """Test that the error can be raised and caught as an Exception."""
        with __import__("pytest").raises(UiPathFaultedTriggerError, match="boom"):
            raise UiPathFaultedTriggerError(
                category=ErrorCategory.DEPLOYMENT,
                message="boom",
            )


class TestUiPathPendingTriggerError:
    """Test UiPathPendingTriggerError inherits correctly."""

    def test_inherits_faulted_trigger_error(self) -> None:
        """Test that PendingTriggerError is a subclass of FaultedTriggerError."""
        err = UiPathPendingTriggerError(
            category=ErrorCategory.UNKNOWN,
            message="Pending",
            detail="waiting for response",
        )
        assert isinstance(err, UiPathFaultedTriggerError)
        assert err.category == ErrorCategory.UNKNOWN
        assert str(err) == "Pending: waiting for response"

    def test_catchable_as_faulted(self) -> None:
        """Test that PendingTriggerError can be caught as FaultedTriggerError."""
        with __import__("pytest").raises(UiPathFaultedTriggerError):
            raise UiPathPendingTriggerError(
                category=ErrorCategory.USER,
                message="still pending",
            )
