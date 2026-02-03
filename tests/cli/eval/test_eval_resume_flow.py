"""Unit tests for eval resume flow to ensure UiPathExecuteOptions is passed correctly."""

import uuid
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
from uipath._cli._utils._eval_set import EvalHelpers
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
    """Test that execute_runtime respects resume=False setting."""
    # Arrange
    from uipath._cli._evals._models._evaluation_set import EvaluationItem

    event_bus = EventBus()
    trace_manager = UiPathTraceManager()

    # Load evaluation set
    eval_set_path = str(Path(__file__).parent / "evals" / "eval-sets" / "default.json")
    evaluation_set, _ = EvalHelpers.load_eval_set(eval_set_path)

    # Create a mock runtime to get schema
    mock_runtime = AsyncMock(spec=UiPathRuntimeProtocol)
    mock_runtime.execute = AsyncMock(
        return_value=UiPathRuntimeResult(
            output={"result": "success"}, status=UiPathRuntimeStatus.SUCCESSFUL
        )
    )
    mock_runtime.get_schema = AsyncMock()

    runtime_schema = await mock_runtime.get_schema()
    runtime_schema.input = {"type": "object", "properties": {}}
    runtime_schema.output = {"type": "object", "properties": {}}

    # Load evaluators
    evaluators = await EvalHelpers.load_evaluators(
        eval_set_path, evaluation_set, agent_model=None
    )

    # Set up context
    context = UiPathEvalContext()
    context.execution_id = str(uuid.uuid4())
    context.evaluation_set = evaluation_set
    context.runtime_schema = runtime_schema
    context.evaluators = evaluators
    context.resume = False  # Test resume=False

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
            eval_item=eval_item, execution_id="test-exec-id"
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
    """Test that execute_runtime respects resume=True setting."""
    # Arrange
    from uipath._cli._evals._models._evaluation_set import EvaluationItem

    event_bus = EventBus()
    trace_manager = UiPathTraceManager()

    # Load evaluation set
    eval_set_path = str(Path(__file__).parent / "evals" / "eval-sets" / "default.json")
    evaluation_set, _ = EvalHelpers.load_eval_set(eval_set_path)

    # Create a mock runtime
    mock_runtime = AsyncMock(spec=UiPathRuntimeProtocol)
    mock_runtime.execute = AsyncMock(
        return_value=UiPathRuntimeResult(
            output={"result": "success"}, status=UiPathRuntimeStatus.SUCCESSFUL
        )
    )
    mock_runtime.get_schema = AsyncMock()

    runtime_schema = await mock_runtime.get_schema()
    runtime_schema.input = {"type": "object", "properties": {}}
    runtime_schema.output = {"type": "object", "properties": {}}

    # Load evaluators
    evaluators = await EvalHelpers.load_evaluators(
        eval_set_path, evaluation_set, agent_model=None
    )

    # Set up context
    context = UiPathEvalContext()
    context.execution_id = str(uuid.uuid4())
    context.evaluation_set = evaluation_set
    context.runtime_schema = runtime_schema
    context.evaluators = evaluators
    context.resume = True  # Test resume=True

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
            eval_item=eval_item, execution_id="test-exec-id"
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

    # Load evaluation set with multiple evals
    eval_set_path = str(
        Path(__file__).parent / "evals" / "eval-sets" / "multiple-evals.json"
    )
    evaluation_set, _ = EvalHelpers.load_eval_set(eval_set_path)

    # Create a mock runtime
    mock_runtime = AsyncMock(spec=UiPathRuntimeProtocol)
    mock_runtime.get_schema = AsyncMock()
    runtime_schema = await mock_runtime.get_schema()
    runtime_schema.input = {"type": "object", "properties": {}}
    runtime_schema.output = {"type": "object", "properties": {}}

    # Load evaluators
    evaluators = await EvalHelpers.load_evaluators(
        eval_set_path, evaluation_set, agent_model=None
    )

    # Set up context
    context = UiPathEvalContext()
    context.execution_id = str(uuid.uuid4())
    context.evaluation_set = evaluation_set
    context.runtime_schema = runtime_schema
    context.evaluators = evaluators
    context.resume = True  # Enable resume mode

    # Create a mock factory
    mock_factory = AsyncMock(spec=UiPathRuntimeFactoryProtocol)
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
        await eval_runtime.initiate_evaluation()
