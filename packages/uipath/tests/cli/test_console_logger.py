"""Tests for ConsoleLogger (CLI logging) current and JSON mode behavior."""

import json

import click
import pytest
from click.testing import CliRunner

from uipath._cli._utils._console import CLIError, ConsoleLogger, LogLevel, OutputMode


@pytest.fixture(autouse=True)
def reset_console_singleton():
    """Reset ConsoleLogger singleton between tests."""
    ConsoleLogger._instance = None
    yield
    ConsoleLogger._instance = None


@pytest.fixture
def console():
    return ConsoleLogger()


class TestSingleton:
    def test_returns_same_instance(self):
        a = ConsoleLogger()
        b = ConsoleLogger()
        assert a is b

    def test_get_instance_returns_singleton(self):
        instance = ConsoleLogger.get_instance()
        assert instance is ConsoleLogger()

    def test_get_instance_creates_if_none(self):
        assert ConsoleLogger._instance is None
        instance = ConsoleLogger.get_instance()
        assert instance is not None


class TestLogOutput:
    def test_info_writes_to_stdout(self, console):
        @click.command()
        def cmd():
            console.info("hello world")

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert result.exit_code == 0
        assert "hello world" in result.output

    def test_success_writes_to_stdout(self, console):
        @click.command()
        def cmd():
            console.success("it worked")

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert result.exit_code == 0
        assert "it worked" in result.output

    def test_warning_writes_to_stdout(self, console):
        @click.command()
        def cmd():
            console.warning("be careful")

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert result.exit_code == 0
        assert "be careful" in result.output

    def test_hint_writes_to_stdout(self, console):
        @click.command()
        def cmd():
            console.hint("try this")

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert result.exit_code == 0
        assert "try this" in result.output

    def test_magic_writes_to_stdout(self, console):
        @click.command()
        def cmd():
            console.magic("sparkles")

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert result.exit_code == 0
        assert "sparkles" in result.output


class TestErrorBehavior:
    def test_error_exits_with_code_1(self, console):
        @click.command()
        def cmd():
            console.error("something broke")

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert result.exit_code == 1

    def test_error_message_in_output(self, console):
        @click.command()
        def cmd():
            console.error("something broke")

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert "something broke" in result.output

    def test_error_with_traceback(self, console):
        @click.command()
        def cmd():
            try:
                raise ValueError("root cause")
            except ValueError:
                console.error("wrapper message", include_traceback=True)

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert result.exit_code == 1
        assert "wrapper message" in result.output
        assert "root cause" in result.output


class TestSpinner:
    def test_spinner_context_manager(self, console):
        @click.command()
        def cmd():
            with console.spinner("loading..."):
                pass
            console.info("done")

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert result.exit_code == 0
        assert "done" in result.output

    def test_spinner_stops_on_exception(self, console):
        @click.command()
        def cmd():
            try:
                with console.spinner("loading..."):
                    raise RuntimeError("boom")
            except RuntimeError:
                pass
            console.info("recovered")

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert result.exit_code == 0
        assert "recovered" in result.output


class TestDisplayOptions:
    def test_display_options_shows_items(self, console):
        @click.command()
        def cmd():
            console.display_options(["alpha", "beta", "gamma"], "Pick one:")

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert result.exit_code == 0
        assert "alpha" in result.output
        assert "0:" in result.output


class TestLink:
    def test_link_includes_url(self, console):
        @click.command()
        def cmd():
            console.link("Click here:", "https://example.com")

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert result.exit_code == 0
        assert "https://example.com" in result.output


class TestLogLevels:
    def test_info_level_has_no_emoji(self):
        assert LogLevel.INFO.value == ""

    def test_warning_level_has_emoji(self):
        assert LogLevel.WARNING.value == "\u26a0\ufe0f"

    def test_error_level_has_emoji(self):
        assert LogLevel.ERROR.value == "\u274c"


class TestConsoleLoggerJsonMode:
    """Tests for ConsoleLogger with OutputMode.JSON."""

    def test_default_output_mode_is_text(self):
        logger = ConsoleLogger()
        assert logger.output_mode is OutputMode.TEXT

    def test_set_output_mode_json(self):
        logger = ConsoleLogger()
        logger.output_mode = OutputMode.JSON
        assert logger.output_mode is OutputMode.JSON

    def test_info_in_json_mode_does_not_print(self):
        @click.command()
        def cmd():
            logger = ConsoleLogger()
            logger.output_mode = OutputMode.JSON
            logger.info("should not appear")

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert "should not appear" not in result.output

    def test_success_in_json_mode_stores_message(self):
        @click.command()
        def cmd():
            logger = ConsoleLogger()
            logger.output_mode = OutputMode.JSON
            logger.success("it worked")
            assert len(logger._messages) == 1
            assert logger._messages[0]["level"] == "success"
            assert logger._messages[0]["message"] == "it worked"

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert result.exit_code == 0

    def test_error_in_json_mode_raises_cli_error(self):
        logger = ConsoleLogger()
        logger.output_mode = OutputMode.JSON
        with pytest.raises(CLIError) as exc_info:
            logger.error("something broke")
        assert exc_info.value.message == "something broke"

    def test_error_in_json_mode_with_traceback(self):
        logger = ConsoleLogger()
        logger.output_mode = OutputMode.JSON
        try:
            raise ValueError("root cause")
        except ValueError:
            with pytest.raises(CLIError) as exc_info:
                logger.error("wrapper", include_traceback=True)
            assert "root cause" in exc_info.value.message

    def test_set_result_stores_data(self):
        logger = ConsoleLogger()
        logger.output_mode = OutputMode.JSON
        logger.set_result({"key": "bucket1", "name": "Production"})
        assert logger._result == {"key": "bucket1", "name": "Production"}

    def test_emit_success_json(self):
        @click.command()
        def cmd():
            logger = ConsoleLogger()
            logger.output_mode = OutputMode.JSON
            logger.info("loading...")
            logger.set_result({"name": "test"})
            logger.emit()

        runner = CliRunner()
        result = runner.invoke(cmd)
        output = json.loads(result.output)
        assert output["status"] == "success"
        assert output["data"] == {"name": "test"}
        assert len(output["messages"]) == 1
        assert output["messages"][0]["level"] == "info"

    def test_emit_success_without_data(self):
        @click.command()
        def cmd():
            logger = ConsoleLogger()
            logger.output_mode = OutputMode.JSON
            logger.success("done")
            logger.emit()

        runner = CliRunner()
        result = runner.invoke(cmd)
        output = json.loads(result.output)
        assert output["status"] == "success"
        assert "data" not in output
        assert len(output["messages"]) == 1

    def test_emit_in_text_mode_is_noop(self):
        @click.command()
        def cmd():
            logger = ConsoleLogger()
            logger.emit()
            click.echo("still works")

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert "still works" in result.output

    def test_spinner_in_json_mode_is_noop(self):
        @click.command()
        def cmd():
            logger = ConsoleLogger()
            logger.output_mode = OutputMode.JSON
            with logger.spinner("loading..."):
                pass
            logger.emit()

        runner = CliRunner()
        result = runner.invoke(cmd)
        output = json.loads(result.output)
        assert output["status"] == "success"

    def test_warning_in_json_mode_stores_message(self):
        @click.command()
        def cmd():
            logger = ConsoleLogger()
            logger.output_mode = OutputMode.JSON
            logger.warning("be careful")
            assert logger._messages[0]["level"] == "warning"

        runner = CliRunner()
        result = runner.invoke(cmd)
        assert result.exit_code == 0

    def test_prompt_in_json_mode_raises_cli_error(self):
        logger = ConsoleLogger()
        logger.output_mode = OutputMode.JSON
        with pytest.raises(CLIError) as exc_info:
            logger.prompt("Enter name")
        assert "Interactive prompt not supported" in exc_info.value.message

    def test_confirm_in_json_mode_raises_cli_error(self):
        logger = ConsoleLogger()
        logger.output_mode = OutputMode.JSON
        with pytest.raises(CLIError) as exc_info:
            logger.confirm("Are you sure?")
        assert "Interactive confirm not supported" in exc_info.value.message


class TestCLIError:
    def test_cli_error_has_message(self):
        err = CLIError("test error")
        assert err.message == "test error"
        assert str(err) == "test error"

    def test_cli_error_stores_collected_messages(self):
        messages = [{"level": "info", "message": "step 1"}]
        err = CLIError("failed", messages=messages)
        assert err.messages == messages


class TestLazyGroupJsonOutput:
    """Tests for LazyGroup JSON output integration."""

    def test_cli_help_with_format_json_still_works(self):
        """--format json --help still produces help output without crashing."""
        from uipath._cli import cli

        runner = CliRunner()
        result = runner.invoke(cli, ["--format", "json", "--help"])
        assert result.exit_code == 0
        # Help output is produced (either JSON or text depending on sys.argv)
        assert len(result.output) > 0

    def test_cli_error_structure(self):
        """CLIError creates proper error output structure."""
        logger = ConsoleLogger()
        logger.output_mode = OutputMode.JSON
        logger.info("step 1")

        error = CLIError("auth failed", messages=logger._messages)

        error_output = {
            "status": "error",
            "error": error.message,
            "messages": error.messages,
        }
        assert error_output["status"] == "error"
        assert error_output["error"] == "auth failed"
        assert len(error_output["messages"]) == 1


class TestOutputModeEnum:
    def test_text_value(self):
        assert OutputMode.TEXT.value == "text"

    def test_json_value(self):
        assert OutputMode.JSON.value == "json"

    def test_csv_value(self):
        assert OutputMode.CSV.value == "csv"
