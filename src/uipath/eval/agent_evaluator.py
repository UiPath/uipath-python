"""Agent evaluation module for running and evaluating agent performance."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional, TypeVar

from uipath.eval.evaluators import BaseEvaluator

from ..tracing import FileExporter
from .models import AgentExecutionOutput, EvalItemResult


class AgentEvaluator:
    """Evaluates agent performance using multiple evaluators.

    This class runs an agent with given inputs and evaluates the outputs
    using registered evaluators. It can yield results as they become available
    or collect all results together.
    """

    def __init__(
        self,
        evaluators: List[BaseEvaluator],
        path_to_agent: str,
        entrypoint: Optional[str] = None,
    ) -> None:
        """Initialize the AgentEvaluator.

        Args:
            evaluators: List of evaluators to run against agent output
            path_to_agent: Path to the agent directory
            entrypoint: Optional custom entrypoint file, auto-discovered if not provided
        """
        os.chdir(path_to_agent)
        if not entrypoint:
            from ._helpers import auto_discover_entrypoint

            self._entrypoint = auto_discover_entrypoint()
        else:
            self._entrypoint = entrypoint

        self._evaluators = evaluators
        self._ensure_models_rebuilt()

    def add_evaluator(self, evaluator: BaseEvaluator) -> None:
        """Add an evaluator to the list of evaluators."""
        self._evaluators.append(evaluator)

    def _ensure_models_rebuilt(self):
        """Ensure all models with forward references are rebuilt."""
        EvalItemResult.model_rebuild(_types_namespace={"BaseEvaluator": BaseEvaluator})

    def _validate_evaluation_criteria(self, evaluation_criteria: Dict[type, Any]) -> None:
        """Validate that all registered evaluators have corresponding evaluation criteria.

        Args:
            evaluation_criteria: Dictionary mapping evaluator classes to their criteria
        """
        evaluator_classes = {type(evaluator) for evaluator in self._evaluators}
        criteria_classes = set(evaluation_criteria.keys())

        missing_criteria = evaluator_classes - criteria_classes
        if missing_criteria:
            missing_names = [cls.__name__ for cls in missing_criteria]
            print(f"Warning: Missing evaluation criteria for evaluator classes: {missing_names}")

        extra_criteria = criteria_classes - evaluator_classes
        if extra_criteria:
            extra_names = [cls.__name__ for cls in extra_criteria]
            print(f"Warning: Extra evaluation criteria found for non-registered evaluator classes: {extra_names}")

    async def run(
        self,
        evaluation_criteria: dict[type, Any],
        agent_input: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[EvalItemResult, None]:
        """Run the agent and yield execution info, then evaluation results as they become available.

        Args:
            evaluation_criteria: Dictionary mapping evaluator classes to their evaluation criteria
            agent_input: Optional input to pass to the agent

        Yields:
            AgentExecutionResult: First, the agent execution information
            EvalItemResult: Then, individual evaluation results as they complete
        """
        # Validate that all evaluators have corresponding criteria
        self._validate_evaluation_criteria(evaluation_criteria)

        loop = asyncio.get_running_loop()
        agent_execution_output = await loop.run_in_executor(
            None, self._run_agent, agent_input
        )

        # yield evaluation results as they complete
        async for eval_result in self._run_evaluators(
            agent_execution_output, agent_input, evaluation_criteria
        ):
            yield eval_result

    async def _run_evaluators(
        self,
        agent_execution_output: AgentExecutionOutput,
        agent_input: Optional[dict[str, Any]],
        evaluation_criteria: dict[type, Any],
    ) -> AsyncGenerator[EvalItemResult, None]:
        for evaluator in self._evaluators:
            try:
                # Get evaluation criteria for this specific evaluator
                criteria = evaluation_criteria.get(type(evaluator))

                if not criteria:
                    raise RuntimeError(f"Evaluation criteria not defined for: {evaluator.name}")
                result = await evaluator.evaluate(
                    agent_input=agent_input,
                    evaluation_criteria=criteria,
                    actual_output=self._extract_target_output(
                        agent_execution_output.actual_output,
                        evaluator.target_output_key,
                    ),
                    execution_logs=agent_execution_output.execution_logs,
                    uipath_eval_spans=agent_execution_output.uipath_spans,
                )
            except Exception as e:
                from uipath.eval.models import EvaluationResult, ScoreType

                result = EvaluationResult(
                    score=0.0,
                    score_type=ScoreType.ERROR,
                    details=f"Evaluation failed: {str(e)}",
                )

            eval_item_result = EvalItemResult(
                evaluator=evaluator,
                result=result,
            )

            yield eval_item_result

    async def run_and_collect(
        self,
        evaluation_criteria: dict[type, Any],
        agent_input: Optional[dict[str, Any]] = None,
    ) -> list[EvalItemResult]:
        """Run the agent and collect all evaluation results.

        This is a convenience method that collects all results from the generator
        into a single EvalItemResults list.

        Args:
            evaluation_criteria: Dictionary mapping evaluator names to their evaluation criteria
            agent_input: Optional input to pass to the agent

        Returns:
            list[EvalItemResult]: All evaluation results collected together
        """
        eval_results: list[EvalItemResult] = []

        async for result in self.run(evaluation_criteria, agent_input):
            eval_results.append(result)

        return eval_results

    def _run_agent(
        self,
        agent_input: Optional[dict[str, Any]] = None,
    ) -> AgentExecutionOutput:
        from .._cli.cli_run import run_core  # type: ignore

        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                import time

                output_file = Path(tmpdir) / "output.json"
                logs_file = Path(tmpdir) / "execution.log"
                trace_file = Path(tmpdir) / "trace.jsonl"

                start_time = time.time()
                success, error_message, info_message = run_core(
                    entrypoint=self._entrypoint,
                    input=json.dumps(agent_input),
                    resume=False,
                    input_file=None,
                    execution_output_file=output_file,
                    logs_file=logs_file,
                    runtime_dir=tmpdir,
                    is_eval_run=True,
                    trace_file=trace_file,
                )
                execution_time = time.time() - start_time
                if not success:
                    raise RuntimeError(f"Agent execution failed: {error_message}")
                else:
                    with open(output_file, "r", encoding="utf-8") as f:
                        result = json.load(f)

                    # for backwards compatibility
                    logs = ""
                    if os.path.isdir(logs_file):
                        with open(logs_file, "r", encoding="utf-8") as f:
                            logs = f.read()

                    uipath_spans = []
                    if os.path.isdir(trace_file):
                        uipath_spans = FileExporter.read_all_spans(trace_file)

                    return AgentExecutionOutput(
                        actual_output=result,
                        execution_time=execution_time,
                        uipath_spans=uipath_spans,
                        execution_logs=logs,
                    )

            except Exception as e:
                raise RuntimeError(str(e)) from e

    def _extract_target_output(
        self, output: Dict[str, Any], target_output_key: str
    ) -> Any:
        if target_output_key != "*":
            if target_output_key not in output:
                raise ValueError(f"Field '{target_output_key}' missing from output")
            output = output[target_output_key]
        return output
