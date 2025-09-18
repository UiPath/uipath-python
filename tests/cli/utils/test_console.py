from unittest.mock import MagicMock, patch

from src.uipath._cli._utils._console import (
    ConsoleLogger,
    EvaluationProgressManager,
    LogLevel,
)


def test_singleton():
    logger1 = ConsoleLogger.get_instance()
    logger2 = ConsoleLogger.get_instance()
    assert logger1 is logger2, "ConsoleLogger should be a singleton"


@patch("click.echo")
def test_log_levels(mock_echo):
    logger = ConsoleLogger.get_instance()
    messages = [
        ("info message", LogLevel.INFO),
        ("success message", LogLevel.SUCCESS),
        ("warning message", LogLevel.WARNING),
        ("error message", LogLevel.ERROR),
        ("hint message", LogLevel.HINT),
        ("magic message", LogLevel.MAGIC),
        ("config message", LogLevel.CONFIG),
        ("select message", LogLevel.SELECT),
        ("link message", LogLevel.LINK, "blue"),
    ]

    for msg in messages:
        if len(msg) == 2:
            logger.log(msg[0], msg[1])
        else:
            logger.log(msg[0], msg[1], fg=msg[2])

    assert mock_echo.call_count == 9


@patch("click.prompt", return_value="user_input")
def test_prompt(mock_prompt):
    logger = ConsoleLogger.get_instance()
    result = logger.prompt("Enter something")
    assert result == "user_input"
    mock_prompt.assert_called_once()


@patch("click.echo")
def test_display_options(mock_echo):
    logger = ConsoleLogger.get_instance()
    options = ["opt1", "opt2"]
    logger.display_options(options)
    # 1 for header, 2 for options
    assert mock_echo.call_count == 3


@patch("src.uipath._cli._utils._console.Progress")
def test_evaluation_progress(mock_progress_class):
    class MockTask:
        def __init__(self, name, total):
            self.name = name
            self.total = total
            self.completed = 0
            self.description = name

    class MockProgressContext:
        def __init__(self):
            self.tasks = {}

        def add_task(self, name, total=1):
            task_id = len(self.tasks) + 1
            self.tasks[task_id] = MockTask(name, total)
            return task_id

        def update(self, task_id, completed=0, description=None):
            task = self.tasks.get(task_id)
            if task:
                task.completed = completed
                if description:
                    task.description = description

        def start(self):
            pass

        def stop(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

    mock_progress_class.return_value = MockProgressContext()
    evaluations = [
        {"id": "1", "name": "Test Eval 1"},
        {"id": "2", "name": "Test Eval 2"},
    ]
    logger = ConsoleLogger.get_instance()
    with logger.evaluation_progress(evaluations) as manager:
        assert isinstance(manager, EvaluationProgressManager)
        manager.complete_evaluation("1")
        manager.fail_evaluation("2", "Failed")


@patch("src.uipath._cli._utils._console.click.get_current_context")
@patch("src.uipath._cli._utils._console.click.echo")
def test_error_exit(mock_echo, mock_context):
    
    # MagicMock for ctx.exit
    mock_ctx = mock_context.return_value
    mock_ctx.exit = MagicMock()

    logger = ConsoleLogger.get_instance()
    logger.error("error message", include_traceback=False)

    # Check that ctx.exit got called instead of builtins.exit
    mock_ctx.exit.assert_called_once_with(1)


@patch("click.prompt", return_value="")
def test_prompt_empty_input(mock_prompt):
    logger = ConsoleLogger.get_instance()
    result = logger.prompt("Enter something")
    assert result == "", "Prompt should handle empty input gracefully"


@patch("click.echo")
def test_log_with_custom_fg_bg(mock_echo):
    logger = ConsoleLogger.get_instance()
    logger.log("custom message", LogLevel.INFO, fg="red", bg="yellow")
    mock_echo.assert_called_once()


@patch("click.echo")
def test_display_options_empty(mock_echo):
    logger = ConsoleLogger.get_instance()
    logger.display_options([])
    # Only header is printed even if no options
    assert mock_echo.call_count == 1
