# type: ignore
"""Tests for conflict handlers used in push and pull operations."""

import os
import tempfile
from pathlib import Path


class TestInteractiveConflictHandler:
    """Tests for InteractiveConflictHandler used during pull operations."""

    def test_should_overwrite_with_user_confirmation(self, monkeypatch):
        """Test that handler returns True when user confirms overwrite."""
        from uipath._cli._utils._project_files import InteractiveConflictHandler

        # Create a temporary file to test with
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            temp_file = Path(f.name)

        try:
            handler = InteractiveConflictHandler(operation="pull")

            # Mock click.confirm to return True
            monkeypatch.setattr("click.confirm", lambda *args, **kwargs: True)

            # Mock click.echo to capture output
            outputs = []
            monkeypatch.setattr(
                "click.echo", lambda msg, **kwargs: outputs.append(str(msg))
            )

            result = handler.should_overwrite(
                "test/file.py",
                "local_hash",
                "remote_hash",
                local_full_path=temp_file,
            )

            assert result is True
            # Check that the warning message was displayed
            assert any("has different content on remote" in str(out) for out in outputs)
        finally:
            os.unlink(temp_file)

    def test_should_overwrite_with_user_rejection(self, monkeypatch):
        """Test that handler returns False when user rejects overwrite."""
        from uipath._cli._utils._project_files import InteractiveConflictHandler

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            temp_file = Path(f.name)

        try:
            handler = InteractiveConflictHandler(operation="pull")

            # Mock click.confirm to return False
            monkeypatch.setattr("click.confirm", lambda *args, **kwargs: False)

            outputs = []
            monkeypatch.setattr(
                "click.echo", lambda msg, **kwargs: outputs.append(str(msg))
            )

            result = handler.should_overwrite(
                "test/file.py",
                "local_hash",
                "remote_hash",
                local_full_path=temp_file,
            )

            assert result is False
        finally:
            os.unlink(temp_file)

    def test_should_overwrite_prompt_message_for_pull(self, monkeypatch):
        """Test that prompt message is appropriate for pull operation."""
        from uipath._cli._utils._project_files import InteractiveConflictHandler

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            temp_file = Path(f.name)

        try:
            handler = InteractiveConflictHandler(operation="pull")

            # Capture the prompt message
            prompt_messages = []

            def mock_confirm(msg, *args, **kwargs):
                prompt_messages.append(msg)
                return True

            monkeypatch.setattr("click.confirm", mock_confirm)
            monkeypatch.setattr("click.echo", lambda *args, **kwargs: None)

            handler.should_overwrite(
                "test/file.py",
                "local_hash",
                "remote_hash",
                local_full_path=temp_file,
            )

            # Verify the prompt message is for pull (overwrite local with remote)
            assert len(prompt_messages) == 1
            assert (
                "overwrite the local file with the remote version" in prompt_messages[0]
            )
        finally:
            os.unlink(temp_file)

    def test_should_overwrite_without_file_path(self, monkeypatch):
        """Test handler behavior when no file path is provided."""
        from uipath._cli._utils._project_files import InteractiveConflictHandler

        handler = InteractiveConflictHandler(operation="pull")

        monkeypatch.setattr("click.confirm", lambda *args, **kwargs: True)

        outputs = []
        monkeypatch.setattr(
            "click.echo", lambda msg, **kwargs: outputs.append(str(msg))
        )

        result = handler.should_overwrite(
            "test/file.py",
            "local_hash",
            "remote_hash",
            local_full_path=None,
        )

        assert result is True
        # Should still show warning but not modification date
        assert any("has different content on remote" in str(out) for out in outputs)
        assert not any("Local file last modified:" in str(out) for out in outputs)

    def test_handler_with_explicit_pull_operation(self, monkeypatch):
        """Test that handler with operation='pull' shows correct prompt."""
        from uipath._cli._utils._project_files import InteractiveConflictHandler

        handler = InteractiveConflictHandler(operation="pull")

        # Capture the prompt message
        prompt_messages = []

        def mock_confirm(msg, *args, **kwargs):
            prompt_messages.append(msg)
            return True

        monkeypatch.setattr("click.confirm", mock_confirm)
        monkeypatch.setattr("click.echo", lambda *args, **kwargs: None)

        result = handler.should_overwrite(
            "test/file.py",
            "local_hash",
            "remote_hash",
        )

        assert result is True
        assert len(prompt_messages) == 1
        assert "overwrite the local file with the remote version" in prompt_messages[0]

    def test_handler_with_explicit_push_operation(self, monkeypatch):
        """Test that handler with operation='push' shows correct prompt."""
        from uipath._cli._utils._project_files import InteractiveConflictHandler

        handler = InteractiveConflictHandler(operation="push")

        # Capture the prompt message
        prompt_messages = []

        def mock_confirm(msg, *args, **kwargs):
            prompt_messages.append(msg)
            return True

        monkeypatch.setattr("click.confirm", mock_confirm)
        monkeypatch.setattr("click.echo", lambda *args, **kwargs: None)

        result = handler.should_overwrite(
            "test/file.py",
            "local_hash",
            "remote_hash",
        )

        assert result is True
        assert len(prompt_messages) == 1
        assert "push and overwrite the remote file" in prompt_messages[0]
        assert "local version" in prompt_messages[0]

    def test_no_modification_timestamp_displayed(self, monkeypatch):
        """Test that modification timestamp is never displayed."""
        from uipath._cli._utils._project_files import InteractiveConflictHandler

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            temp_file = Path(f.name)

        try:
            handler = InteractiveConflictHandler(operation="pull")

            monkeypatch.setattr("click.confirm", lambda *args, **kwargs: True)

            outputs = []
            monkeypatch.setattr(
                "click.echo", lambda msg, **kwargs: outputs.append(str(msg))
            )

            handler.should_overwrite(
                "test/file.py",
                "local_hash",
                "remote_hash",
                local_full_path=temp_file,
            )

            # Verify that no modification timestamp is displayed
            assert not any("Local file last modified:" in str(out) for out in outputs)
            assert not any("last modified" in str(out).lower() for out in outputs)
        finally:
            os.unlink(temp_file)


class TestAlwaysOverwriteHandler:
    """Tests for AlwaysOverwriteHandler."""

    def test_always_returns_true(self):
        """Test that AlwaysOverwriteHandler always returns True."""
        from uipath._cli._utils._project_files import AlwaysOverwriteHandler

        handler = AlwaysOverwriteHandler()
        assert handler.should_overwrite("file.py", "hash1", "hash2") is True
        assert (
            handler.should_overwrite("other.py", "hash3", "hash4", Path("test.py"))
            is True
        )


class TestAlwaysSkipHandler:
    """Tests for AlwaysSkipHandler."""

    def test_always_returns_false(self):
        """Test that AlwaysSkipHandler always returns False."""
        from uipath._cli._utils._project_files import AlwaysSkipHandler

        handler = AlwaysSkipHandler()
        assert handler.should_overwrite("file.py", "hash1", "hash2") is False
        assert (
            handler.should_overwrite("other.py", "hash3", "hash4", Path("test.py"))
            is False
        )
