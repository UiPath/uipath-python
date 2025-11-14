"""Tests for Process model validation - retention fields optional."""

import pytest
from pydantic import ValidationError

from uipath.models.processes import Process


class TestProcessModelRetentionFields:
    """Test Process model handles optional retention fields correctly."""

    def test_process_with_all_retention_fields(self) -> None:
        """Test Process validates with all retention fields present."""
        data = {
            "Key": "process-key-123",
            "ProcessKey": "proc-key",
            "ProcessVersion": "1.0.0",
            "IsLatestVersion": True,
            "IsProcessDeleted": False,
            "Description": "Test process",
            "Name": "TestProcess",
            "ProcessType": "Process",
            "RequiresUserInteraction": False,
            "IsAttended": False,
            "IsCompiled": True,
            "FeedId": "feed-123",
            "JobPriority": "Normal",
            "SpecificPriorityValue": 5000,
            "TargetFramework": "Windows",
            "Id": 1,
            "RetentionAction": "Delete",
            "RetentionPeriod": 30,
            "StaleRetentionAction": "Archive",
            "StaleRetentionPeriod": 90,
            "Tags": [],
        }

        process = Process.model_validate(data)

        assert process.retention_action == "Delete"
        assert process.retention_period == 30
        assert process.stale_retention_action == "Archive"
        assert process.stale_retention_period == 90

    def test_process_without_retention_fields(self) -> None:
        """Test Process validates WITHOUT retention fields (defaults to None)."""
        data = {
            "Key": "process-key-123",
            "ProcessKey": "proc-key",
            "ProcessVersion": "1.0.0",
            "IsLatestVersion": True,
            "IsProcessDeleted": False,
            "Description": "Test process",
            "Name": "TestProcess",
            "ProcessType": "Process",
            "RequiresUserInteraction": False,
            "IsAttended": False,
            "IsCompiled": True,
            "FeedId": "feed-123",
            "JobPriority": "Normal",
            "SpecificPriorityValue": 5000,
            "TargetFramework": "Windows",
            "Id": 1,
            "Tags": [],
            # No retention fields
        }

        process = Process.model_validate(data)

        # Should default to None
        assert process.retention_action is None
        assert process.retention_period is None
        assert process.stale_retention_action is None
        assert process.stale_retention_period is None

    def test_process_with_partial_retention_fields(self) -> None:
        """Test Process validates with only some retention fields."""
        data = {
            "Key": "process-key-123",
            "ProcessKey": "proc-key",
            "ProcessVersion": "1.0.0",
            "IsLatestVersion": True,
            "IsProcessDeleted": False,
            "Description": "Test process",
            "Name": "TestProcess",
            "ProcessType": "Process",
            "RequiresUserInteraction": False,
            "IsAttended": False,
            "IsCompiled": True,
            "FeedId": "feed-123",
            "JobPriority": "Normal",
            "SpecificPriorityValue": 5000,
            "TargetFramework": "Windows",
            "Id": 1,
            "Tags": [],
            # Only retention_action, not retention_period
            "RetentionAction": "Delete",
        }

        process = Process.model_validate(data)

        assert process.retention_action == "Delete"
        assert process.retention_period is None  # Missing field defaults to None

    def test_process_with_null_retention_fields(self) -> None:
        """Test Process validates with explicitly null retention fields."""
        data = {
            "Key": "process-key-123",
            "ProcessKey": "proc-key",
            "ProcessVersion": "1.0.0",
            "IsLatestVersion": True,
            "IsProcessDeleted": False,
            "Description": "Test process",
            "Name": "TestProcess",
            "ProcessType": "Process",
            "RequiresUserInteraction": False,
            "IsAttended": False,
            "IsCompiled": True,
            "FeedId": "feed-123",
            "JobPriority": "Normal",
            "SpecificPriorityValue": 5000,
            "TargetFramework": "Windows",
            "Id": 1,
            "Tags": [],
            # Explicitly null
            "RetentionAction": None,
            "RetentionPeriod": None,
            "StaleRetentionAction": None,
            "StaleRetentionPeriod": None,
        }

        process = Process.model_validate(data)

        assert process.retention_action is None
        assert process.retention_period is None
        assert process.stale_retention_action is None
        assert process.stale_retention_period is None

    @pytest.mark.parametrize(
        "retention_action,retention_period",
        [
            ("Delete", 30),
            ("Archive", 60),
            (None, None),
            ("Delete", None),  # Action without period
            (None, 30),  # Period without action (weird but valid)
        ],
    )
    def test_process_retention_combinations(
        self, retention_action: str | None, retention_period: int | None
    ) -> None:
        """Test Process validates with various retention field combinations."""
        data = {
            "Key": "process-key-123",
            "ProcessKey": "proc-key",
            "ProcessVersion": "1.0.0",
            "IsLatestVersion": True,
            "IsProcessDeleted": False,
            "Description": "Test process",
            "Name": "TestProcess",
            "ProcessType": "Process",
            "RequiresUserInteraction": False,
            "IsAttended": False,
            "IsCompiled": True,
            "FeedId": "feed-123",
            "JobPriority": "Normal",
            "SpecificPriorityValue": 5000,
            "TargetFramework": "Windows",
            "Id": 1,
            "Tags": [],
        }

        # Add retention fields if not None
        if retention_action is not None:
            data["RetentionAction"] = retention_action
        if retention_period is not None:
            data["RetentionPeriod"] = retention_period

        process = Process.model_validate(data)

        assert process.retention_action == retention_action
        assert process.retention_period == retention_period

    @pytest.mark.parametrize(
        "stale_retention_action,stale_retention_period",
        [
            ("Delete", 30),
            ("Archive", 90),
            (None, None),
            ("Archive", None),  # Action without period
            (None, 60),  # Period without action
        ],
    )
    def test_process_stale_retention_combinations(
        self, stale_retention_action: str | None, stale_retention_period: int | None
    ) -> None:
        """Test Process validates with various stale retention field combinations."""
        data = {
            "Key": "process-key-123",
            "ProcessKey": "proc-key",
            "ProcessVersion": "1.0.0",
            "IsLatestVersion": True,
            "IsProcessDeleted": False,
            "Description": "Test process",
            "Name": "TestProcess",
            "ProcessType": "Process",
            "RequiresUserInteraction": False,
            "IsAttended": False,
            "IsCompiled": True,
            "FeedId": "feed-123",
            "JobPriority": "Normal",
            "SpecificPriorityValue": 5000,
            "TargetFramework": "Windows",
            "Id": 1,
            "Tags": [],
        }

        # Add stale retention fields if not None
        if stale_retention_action is not None:
            data["StaleRetentionAction"] = stale_retention_action
        if stale_retention_period is not None:
            data["StaleRetentionPeriod"] = stale_retention_period

        process = Process.model_validate(data)

        assert process.stale_retention_action == stale_retention_action
        assert process.stale_retention_period == stale_retention_period

    def test_process_all_retention_combinations(self) -> None:
        """Test Process with all four retention fields in various states."""
        data = {
            "Key": "process-key-123",
            "ProcessKey": "proc-key",
            "ProcessVersion": "1.0.0",
            "IsLatestVersion": True,
            "IsProcessDeleted": False,
            "Description": "Test process",
            "Name": "TestProcess",
            "ProcessType": "Process",
            "RequiresUserInteraction": False,
            "IsAttended": False,
            "IsCompiled": True,
            "FeedId": "feed-123",
            "JobPriority": "Normal",
            "SpecificPriorityValue": 5000,
            "TargetFramework": "Windows",
            "Id": 1,
            "Tags": [],
            "RetentionAction": "Delete",
            "RetentionPeriod": 30,
            "StaleRetentionAction": None,  # Mixed: regular set, stale null
            "StaleRetentionPeriod": None,
        }

        process = Process.model_validate(data)

        assert process.retention_action == "Delete"
        assert process.retention_period == 30
        assert process.stale_retention_action is None
        assert process.stale_retention_period is None

    def test_process_field_alias_mapping(self) -> None:
        """Test Process correctly maps PascalCase API fields to snake_case."""
        data = {
            "Key": "process-key-123",
            "ProcessKey": "proc-key",
            "ProcessVersion": "1.0.0",
            "IsLatestVersion": True,
            "IsProcessDeleted": False,
            "Description": "Test process",
            "Name": "TestProcess",
            "ProcessType": "Process",
            "RequiresUserInteraction": False,
            "IsAttended": False,
            "IsCompiled": True,
            "FeedId": "feed-123",
            "JobPriority": "Normal",
            "SpecificPriorityValue": 5000,
            "TargetFramework": "Windows",
            "Id": 1,
            "Tags": [],
            # API uses PascalCase
            "RetentionAction": "Delete",
            "RetentionPeriod": 30,
        }

        process = Process.model_validate(data)

        # Python uses snake_case
        assert hasattr(process, "retention_action")
        assert hasattr(process, "retention_period")
        assert process.retention_action == "Delete"
        assert process.retention_period == 30

    def test_process_zero_retention_period(self) -> None:
        """Test Process handles zero retention period (edge case)."""
        data = {
            "Key": "process-key-123",
            "ProcessKey": "proc-key",
            "ProcessVersion": "1.0.0",
            "IsLatestVersion": True,
            "IsProcessDeleted": False,
            "Description": "Test process",
            "Name": "TestProcess",
            "ProcessType": "Process",
            "RequiresUserInteraction": False,
            "IsAttended": False,
            "IsCompiled": True,
            "FeedId": "feed-123",
            "JobPriority": "Normal",
            "SpecificPriorityValue": 5000,
            "TargetFramework": "Windows",
            "Id": 1,
            "Tags": [],
            "RetentionPeriod": 0,  # Zero is valid but unusual
        }

        process = Process.model_validate(data)

        assert process.retention_period == 0

    def test_process_negative_retention_period_fails(self) -> None:
        """Test Process rejects negative retention period."""
        data = {
            "Key": "process-key-123",
            "ProcessKey": "proc-key",
            "ProcessVersion": "1.0.0",
            "IsLatestVersion": True,
            "IsProcessDeleted": False,
            "Description": "Test process",
            "Name": "TestProcess",
            "ProcessType": "Process",
            "RequiresUserInteraction": False,
            "IsAttended": False,
            "IsCompiled": True,
            "FeedId": "feed-123",
            "JobPriority": "Normal",
            "SpecificPriorityValue": 5000,
            "TargetFramework": "Windows",
            "Id": 1,
            "Tags": [],
            "RetentionPeriod": -1,  # Negative should fail
        }

        # Model should reject negative retention period
        with pytest.raises(ValidationError) as exc_info:
            Process.model_validate(data)

        # Verify the error is about the RetentionPeriod field
        error_message = str(exc_info.value).lower()
        assert "retentionperiod" in error_message
        assert "greater than or equal to 0" in error_message

    def test_process_negative_stale_retention_period_fails(self) -> None:
        """Test Process rejects negative stale retention period."""
        data = {
            "Key": "process-key-124",
            "ProcessKey": "proc-key",
            "ProcessVersion": "1.0.0",
            "IsLatestVersion": True,
            "IsProcessDeleted": False,
            "Description": "Test process",
            "Name": "TestProcess",
            "ProcessType": "Process",
            "RequiresUserInteraction": False,
            "IsAttended": False,
            "IsCompiled": True,
            "FeedId": "feed-123",
            "JobPriority": "Normal",
            "SpecificPriorityValue": 5000,
            "TargetFramework": "Windows",
            "Id": 1,
            "Tags": [],
            "StaleRetentionPeriod": -5,  # Negative should fail
        }

        # Model should reject negative stale retention period
        with pytest.raises(ValidationError) as exc_info:
            Process.model_validate(data)

        # Verify the error is about the StaleRetentionPeriod field
        error_message = str(exc_info.value).lower()
        assert "staleretentionperiod" in error_message
        assert "greater than or equal to 0" in error_message

    def test_process_large_retention_period(self) -> None:
        """Test Process handles very large retention period values."""
        data = {
            "Key": "process-key-123",
            "ProcessKey": "proc-key",
            "ProcessVersion": "1.0.0",
            "IsLatestVersion": True,
            "IsProcessDeleted": False,
            "Description": "Test process",
            "Name": "TestProcess",
            "ProcessType": "Process",
            "RequiresUserInteraction": False,
            "IsAttended": False,
            "IsCompiled": True,
            "FeedId": "feed-123",
            "JobPriority": "Normal",
            "SpecificPriorityValue": 5000,
            "TargetFramework": "Windows",
            "Id": 1,
            "Tags": [],
            "RetentionPeriod": 3650,  # 10 years in days
            "StaleRetentionPeriod": 7300,  # 20 years
        }

        process = Process.model_validate(data)

        assert process.retention_period == 3650
        assert process.stale_retention_period == 7300

    @pytest.mark.parametrize("action", ["Delete", "Archive", "Keep"])
    def test_process_retention_action_case_sensitive(self, action: str) -> None:
        """Test Process accepts various retention action values."""
        data = {
            "Key": "process-key-123",
            "ProcessKey": "proc-key",
            "ProcessVersion": "1.0.0",
            "IsLatestVersion": True,
            "IsProcessDeleted": False,
            "Description": "Test process",
            "Name": "TestProcess",
            "ProcessType": "Process",
            "RequiresUserInteraction": False,
            "IsAttended": False,
            "IsCompiled": True,
            "FeedId": "feed-123",
            "JobPriority": "Normal",
            "SpecificPriorityValue": 5000,
            "TargetFramework": "Windows",
            "Id": 1,
            "Tags": [],
            "RetentionAction": action,
        }

        process = Process.model_validate(data)
        assert process.retention_action == action

    def test_process_model_serialization_preserves_retention(self) -> None:
        """Test Process serialization includes retention fields."""
        data = {
            "Key": "process-key-123",
            "ProcessKey": "proc-key",
            "ProcessVersion": "1.0.0",
            "IsLatestVersion": True,
            "IsProcessDeleted": False,
            "Description": "Test process",
            "Name": "TestProcess",
            "ProcessType": "Process",
            "RequiresUserInteraction": False,
            "IsAttended": False,
            "IsCompiled": True,
            "FeedId": "feed-123",
            "JobPriority": "Normal",
            "SpecificPriorityValue": 5000,
            "TargetFramework": "Windows",
            "Id": 1,
            "Tags": [],
            "RetentionAction": "Delete",
            "RetentionPeriod": 30,
        }

        process = Process.model_validate(data)
        serialized = process.model_dump(by_alias=True)

        # Should use API field names (PascalCase)
        assert "RetentionAction" in serialized
        assert "RetentionPeriod" in serialized
        assert serialized["RetentionAction"] == "Delete"
        assert serialized["RetentionPeriod"] == 30

    def test_process_none_serialization(self) -> None:
        """Test Process serialization excludes None retention fields."""
        data = {
            "Key": "process-key-123",
            "ProcessKey": "proc-key",
            "ProcessVersion": "1.0.0",
            "IsLatestVersion": True,
            "IsProcessDeleted": False,
            "Description": "Test process",
            "Name": "TestProcess",
            "ProcessType": "Process",
            "RequiresUserInteraction": False,
            "IsAttended": False,
            "IsCompiled": True,
            "FeedId": "feed-123",
            "JobPriority": "Normal",
            "SpecificPriorityValue": 5000,
            "TargetFramework": "Windows",
            "Id": 1,
            "Tags": [],
            # No retention fields
        }

        process = Process.model_validate(data)
        serialized = process.model_dump(by_alias=True, exclude_none=True)

        # Should not include None fields when exclude_none=True
        assert "RetentionAction" not in serialized
        assert "RetentionPeriod" not in serialized
        assert "StaleRetentionAction" not in serialized
        assert "StaleRetentionPeriod" not in serialized
