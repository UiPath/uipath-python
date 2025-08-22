"""Tests for AgentEvaluator."""

import os
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest

from tests.utils.project_details import ProjectDetails
from tests.utils.uipath_json import UiPathJson
from uipath.eval import AgentEvaluator
from uipath.eval.evaluators import BaseEvaluator
from uipath.eval.models import EvalItemResult, EvaluationResult, ScoreType


class MockEvaluator(BaseEvaluator):
    """Mock evaluator for testing."""

    def __init__(
        self,
        name: str = "MockEvaluator",
        score: Any = True,
        score_type: ScoreType = ScoreType.BOOLEAN,
    ):
        super().__init__(name=name)
        self.score = score
        self.score_type = score_type

    async def evaluate(
        self,
        agent_input: Optional[Dict[str, Any]],
        expected_output: Dict[str, Any],
        actual_output: Dict[str, Any],
        uipath_eval_spans: Optional[List[Any]],
        execution_logs: str,
    ) -> EvaluationResult:
        return EvaluationResult(
            score=self.score, score_type=self.score_type, details="Mock evaluation"
        )


@pytest.fixture(params=[False])
def mock_agent_dir(
    temp_dir: str,
    simple_script: str,
    uipath_json: UiPathJson,
    uipath_script_json: UiPathJson,
    project_details: ProjectDetails,
    request,
) -> str:
    """Create a mock agent directory."""
    use_script_config = request.param
    config = uipath_script_json if use_script_config else uipath_json

    with open(os.path.join(temp_dir, "main.py"), "w") as f:
        f.write(simple_script)

    with open(os.path.join(temp_dir, "uipath.json"), "w") as f:
        f.write(config.to_json())

    with open(os.path.join(temp_dir, "pyproject.toml"), "w") as f:
        f.write(project_details.to_toml())

    return temp_dir


@pytest.fixture
def mock_evaluators() -> List[BaseEvaluator]:
    """Create mock evaluators for testing."""
    return [
        MockEvaluator("eval1", True, ScoreType.BOOLEAN),
        MockEvaluator("eval2", 85.5, ScoreType.NUMERICAL),
        MockEvaluator("eval3", False, ScoreType.BOOLEAN),
    ]


class TestAgentEvaluator:
    """Test cases for AgentEvaluator class."""

    @pytest.mark.parametrize("mock_agent_dir", [True], indirect=True)
    def test_autodiscovery_single_entrypoint(
        self, mock_evaluators: List[BaseEvaluator], mock_agent_dir: str
    ):
        """Test AgentEvaluator initialization with evaluators and path."""
        original_cwd = os.getcwd()
        try:
            agent_evaluator = AgentEvaluator(
                evaluators=mock_evaluators, path_to_agent=mock_agent_dir
            )

            assert agent_evaluator._entrypoint == "main.py"
            assert os.getcwd() == mock_agent_dir
        finally:
            os.chdir(original_cwd)

    def test_autodiscovery_multiple_entrypoints(
        self, mock_evaluators: List[BaseEvaluator], mock_agent_dir: str
    ):
        """Test AgentEvaluator initialization with evaluators and path."""
        original_cwd = os.getcwd()
        try:
            with pytest.raises(ValueError) as exception:
                AgentEvaluator(evaluators=mock_evaluators, path_to_agent=mock_agent_dir)

            assert (
                str(exception.value)
                == "Multiple entrypoints found: ['agent_1', 'agent_2']. Please specify which entrypoint to use."
            )
        finally:
            os.chdir(original_cwd)

    def test_init_multiple_entrypoints(
        self, mock_evaluators: List[BaseEvaluator], mock_agent_dir: str
    ):
        """Test AgentEvaluator initialization with evaluators and path."""
        original_cwd = os.getcwd()
        try:
            agent_evaluator = AgentEvaluator(
                evaluators=mock_evaluators,
                entrypoint="agent_1",
                path_to_agent=mock_agent_dir,
            )

            assert len(agent_evaluator._evaluators) == 3
            assert agent_evaluator._entrypoint == "agent_1"
            assert os.getcwd() == mock_agent_dir
        finally:
            os.chdir(original_cwd)

    def test_add_evaluator(
        self, mock_evaluators: List[BaseEvaluator], mock_agent_dir: str
    ):
        """Test adding an evaluator to AgentEvaluator."""
        original_cwd = os.getcwd()
        try:
            evaluator = AgentEvaluator(
                evaluators=mock_evaluators[:2],
                path_to_agent=mock_agent_dir,
                entrypoint="agent_2",
            )

            assert len(evaluator._evaluators) == 2

            # Add third evaluator
            evaluator.add_evaluator(mock_evaluators[2])
            assert len(evaluator._evaluators) == 3
        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_run_basic(
        self, mock_evaluators: List[BaseEvaluator], mock_agent_dir: str
    ):
        """Test basic run functionality."""
        original_cwd = os.getcwd()
        try:
            with patch.object(AgentEvaluator, "_run_agent") as mock_run_agent:
                # Mock the agent execution
                mock_run_agent.return_value = MagicMock(
                    actual_output={"result": "test_output"},
                    execution_logs="test logs",
                    uipath_eval_spans=[],
                )

                evaluator = AgentEvaluator(
                    evaluators=mock_evaluators,
                    path_to_agent=mock_agent_dir,
                    entrypoint="agent_2",
                )

                expected_output = {"result": "expected"}
                agent_input = {"input": "test"}

                results = []
                async for result in evaluator.run(expected_output, agent_input):
                    results.append(result)

                # Should get results from all 3 evaluators
                assert len(results) == 3
                assert all(isinstance(result, EvalItemResult) for result in results)

        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_run_no_agent_input(
        self, mock_evaluators: List[BaseEvaluator], mock_agent_dir: str
    ):
        """Test run with no agent input provided."""
        original_cwd = os.getcwd()
        try:
            with patch.object(AgentEvaluator, "_run_agent") as mock_run_agent:
                # Mock the agent execution
                mock_run_agent.return_value = MagicMock(
                    actual_output={"result": "test_output"},
                    execution_logs="test logs",
                    uipath_eval_spans=[],
                )

                evaluator = AgentEvaluator(
                    evaluators=mock_evaluators,
                    path_to_agent=mock_agent_dir,
                    entrypoint="agent_1",
                )

                expected_output = {"result": "expected"}

                results = []
                async for result in evaluator.run(expected_output):
                    results.append(result)

                assert len(results) == 3
                mock_run_agent.assert_called_once_with(None)

        finally:
            os.chdir(original_cwd)

    @pytest.mark.asyncio
    async def test_run_evaluators_error_handling(
        self, mock_evaluators: List[BaseEvaluator], mock_agent_dir: str
    ):
        """Test error handling in evaluators."""
        original_cwd = os.getcwd()
        try:
            # Create an evaluator that raises an exception
            failing_evaluator = MockEvaluator("failing_eval")

            async def failing_evaluate(*args, **kwargs):
                raise Exception("Evaluation failed")

            failing_evaluator.evaluate = failing_evaluate

            with patch.object(AgentEvaluator, "_run_agent") as mock_run_agent:
                mock_run_agent.return_value = MagicMock(
                    actual_output={"result": "test_output"},
                    execution_logs="test logs",
                    uipath_eval_spans=[],
                )

                evaluator = AgentEvaluator(
                    evaluators=[failing_evaluator],
                    path_to_agent=mock_agent_dir,
                    entrypoint="agent_1",
                )

                expected_output = {"result": "expected"}

                results = []
                async for result in evaluator.run(expected_output):
                    results.append(result)

                # Should handle the error gracefully
                assert len(results) == 1
                assert isinstance(results[0], EvalItemResult)

        finally:
            os.chdir(original_cwd)

    def test_ensure_models_rebuilt(
        self, mock_evaluators: List[BaseEvaluator], mock_agent_dir: str
    ):
        """Test that model rebuilding works correctly."""
        original_cwd = os.getcwd()
        try:
            with patch(
                "uipath.eval.models.EvalItemResult.model_rebuild"
            ) as mock_rebuild:
                AgentEvaluator(
                    evaluators=mock_evaluators,
                    path_to_agent=mock_agent_dir,
                    entrypoint="agent_1",
                )

                mock_rebuild.assert_called_once()

        finally:
            os.chdir(original_cwd)
