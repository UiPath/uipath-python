"""Unit tests for eval resume flow to ensure UiPathExecuteOptions is passed correctly."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeFactoryProtocol,
    UiPathRuntimeProtocol,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)

from uipath._cli._evals._runtime import UiPathEvalContext, UiPathEvalRuntime
from uipath._events._event_bus import EventBus

# ============================================================================
# Direct unit tests using mocks to verify the specific code path we changed
# ============================================================================
#
# These tests directly verify that UiPathExecuteOptions is being passed correctly
# in the execute_runtime method, which is the specific code path we modified.
#


@pytest.mark.asyncio
async def test_execute_runtime_method_passes_options_with_resume_false():
    """Direct test of execute_runtime method to verify UiPathExecuteOptions(resume=False) is passed."""
    # Arrange
    from uipath._cli._evals._models._evaluation_set import EvaluationItem

    event_bus = EventBus()
    trace_manager = UiPathTraceManager()
    context = UiPathEvalContext()
    context.eval_set = str(
        Path(__file__).parent / "evals" / "eval-sets" / "default.json"
    )
    context.resume = False  # Test resume=False

    # Create a mock runtime that will be wrapped
    mock_runtime = AsyncMock(spec=UiPathRuntimeProtocol)
    mock_runtime.execute = AsyncMock(
        return_value=UiPathRuntimeResult(
            output={"result": "success"}, status=UiPathRuntimeStatus.SUCCESSFUL
        )
    )

    # Create a mock factory
    mock_factory = AsyncMock(spec=UiPathRuntimeFactoryProtocol)
    mock_factory.new_runtime = AsyncMock(return_value=mock_runtime)

    eval_runtime = UiPathEvalRuntime(context, mock_factory, trace_manager, event_bus)

    eval_item = EvaluationItem(
        id="test-eval",
        name="Test Evaluation",
        inputs={"foo": "bar"},
        evaluation_criterias={},
    )

    #  Act - Call execute_runtime directly
    with patch(
        "uipath._cli._evals._runtime.UiPathExecutionRuntime"
    ) as mock_execution_runtime_class:
        # Set up the mock to capture the execute call
        mock_execution_runtime_instance = AsyncMock()
        mock_execution_runtime_instance.execute = AsyncMock(
            return_value=UiPathRuntimeResult(
                output={"result": "success"}, status=UiPathRuntimeStatus.SUCCESSFUL
            )
        )
        mock_execution_runtime_class.return_value = mock_execution_runtime_instance

        await eval_runtime.execute_runtime(
            eval_item=eval_item, execution_id="test-exec-id", runtime=mock_runtime
        )

        # Assert - Verify that execute was called with UiPathExecuteOptions(resume=False)
        assert mock_execution_runtime_instance.execute.called
        call_args = mock_execution_runtime_instance.execute.call_args

        # Extract the options argument
        options = call_args.kwargs.get("options") or (
            call_args.args[1] if len(call_args.args) > 1 else None
        )

        # Assert that options were passed and resume=False
        assert options is not None, "UiPathExecuteOptions should be passed explicitly"
        assert isinstance(options, UiPathExecuteOptions)
        assert options.resume is False, (
            "resume should be False when context.resume=False"
        )


@pytest.mark.asyncio
async def test_execute_runtime_method_passes_options_with_resume_true():
    """Direct test of execute_runtime method to verify UiPathExecuteOptions(resume=True) is passed."""
    # Arrange
    from uipath._cli._evals._models._evaluation_set import EvaluationItem

    event_bus = EventBus()
    trace_manager = UiPathTraceManager()
    context = UiPathEvalContext()
    context.eval_set = str(
        Path(__file__).parent / "evals" / "eval-sets" / "default.json"
    )
    context.resume = True  # Test resume=True

    # Create a mock runtime
    mock_runtime = AsyncMock(spec=UiPathRuntimeProtocol)
    mock_runtime.execute = AsyncMock(
        return_value=UiPathRuntimeResult(
            output={"result": "success"}, status=UiPathRuntimeStatus.SUCCESSFUL
        )
    )

    # Create a mock factory
    mock_factory = AsyncMock(spec=UiPathRuntimeFactoryProtocol)
    mock_factory.new_runtime = AsyncMock(return_value=mock_runtime)

    eval_runtime = UiPathEvalRuntime(context, mock_factory, trace_manager, event_bus)

    eval_item = EvaluationItem(
        id="test-eval",
        name="Test Evaluation",
        inputs={"foo": "bar"},
        evaluation_criterias={},
    )

    # Act - Call execute_runtime directly
    with patch(
        "uipath._cli._evals._runtime.UiPathExecutionRuntime"
    ) as mock_execution_runtime_class:
        # Set up the mock to capture the execute call
        mock_execution_runtime_instance = AsyncMock()
        mock_execution_runtime_instance.execute = AsyncMock(
            return_value=UiPathRuntimeResult(
                output={"result": "success"}, status=UiPathRuntimeStatus.SUCCESSFUL
            )
        )
        mock_execution_runtime_class.return_value = mock_execution_runtime_instance

        await eval_runtime.execute_runtime(
            eval_item=eval_item, execution_id="test-exec-id", runtime=mock_runtime
        )

        # Assert - Verify that execute was called with UiPathExecuteOptions(resume=True)
        assert mock_execution_runtime_instance.execute.called
        call_args = mock_execution_runtime_instance.execute.call_args

        # Extract the options argument
        options = call_args.kwargs.get("options") or (
            call_args.args[1] if len(call_args.args) > 1 else None
        )

        # Assert that options were passed and resume=True
        assert options is not None, "UiPathExecuteOptions should be passed explicitly"
        assert isinstance(options, UiPathExecuteOptions)
        assert options.resume is True, "resume should be True when context.resume=True"


@pytest.mark.asyncio
async def test_resume_with_multiple_evaluations_raises_error():
    """Test that resume mode with multiple evaluations raises a ValueError."""
    # Arrange
    event_bus = EventBus()
    trace_manager = UiPathTraceManager()
    context = UiPathEvalContext()
    context.eval_set = str(
        Path(__file__).parent / "evals" / "eval-sets" / "multiple-evals.json"
    )
    context.resume = True  # Enable resume mode

    # Create a mock factory
    mock_factory = AsyncMock(spec=UiPathRuntimeFactoryProtocol)
    mock_runtime = AsyncMock(spec=UiPathRuntimeProtocol)
    mock_factory.new_runtime = AsyncMock(return_value=mock_runtime)

    eval_runtime = UiPathEvalRuntime(
        context=context,
        factory=mock_factory,
        event_bus=event_bus,
        trace_manager=trace_manager,
    )

    # Act & Assert
    with pytest.raises(
        ValueError,
        match=r"Resume mode is not supported with multiple evaluations.*Found 2 evaluations",
    ):
        await eval_runtime.initiate_evaluation(mock_runtime)
