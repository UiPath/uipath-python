"""Evaluation service for running and managing evaluation sets."""

import asyncio
import json
import os
import tempfile
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from uipath._cli._utils._console import ConsoleLogger, EvaluationProgressManager

from ..cli_run import run_core  # type: ignore
from ._evaluators._evaluator_base import EvaluatorBase
from ._evaluators._evaluator_factory import EvaluatorFactory
from ._models import (
    EvaluationSet,
    EvaluationSetResult,
)
from ._models._evaluators import EvalItemResult
from .progress_reporter import ProgressReporter

console = ConsoleLogger()


class EvaluationService:
    """Service for running evaluations."""

    def __init__(
        self,
        entrypoint: Optional[str] = None,
        eval_set_path: Optional[str | Path] = None,
        eval_ids: Optional[List[str]] = None,
        workers: int = 8,
        report_progress: bool = True,
    ):
        """Initialize the evaluation service.

        Args:
            entrypoint: Path to the agent script to evaluate (optional, will auto-discover if not provided)
            eval_set_path: Path to the evaluation set file (optional, will auto-discover if not provided)
            workers: Number of parallel workers for running evaluations
            report_progress: Whether to report progress to StudioWeb
        """
        self.entrypoint, self.eval_set_path = self._resolve_paths(
            entrypoint, eval_set_path
        )
        self._eval_set = self._load_eval_set(eval_ids)
        self._evaluators = self._load_evaluators()
        self._num_workers = workers
        self._results_lock = asyncio.Lock()
        self._progress_manager: Optional[EvaluationProgressManager] = None
        self._report_progress = report_progress
        self._progress_reporter: Optional[ProgressReporter] = None
        self._initialize_results()

    def _resolve_paths(
        self, entrypoint: Optional[str], eval_set_path: Optional[str | Path]
    ) -> tuple[str, Path]:
        """Resolve entrypoint and eval_set_path, auto-discovering if not provided.

        Args:
            entrypoint: Optional entrypoint path
            eval_set_path: Optional eval set path

        Returns:
            Tuple of (resolved_entrypoint, resolved_eval_set_path)

        Raises:
            ValueError: If paths cannot be resolved or multiple options exist
        """
        resolved_entrypoint = entrypoint
        resolved_eval_set_path = eval_set_path

        if resolved_entrypoint is None:
            resolved_entrypoint = self._auto_discover_entrypoint()

        if resolved_eval_set_path is None:
            resolved_eval_set_path = self._auto_discover_eval_set()

        eval_set_path_obj = Path(resolved_eval_set_path)
        if not eval_set_path_obj.is_file() or eval_set_path_obj.suffix != ".json":
            raise ValueError("Evaluation set must be a JSON file")

        return resolved_entrypoint, eval_set_path_obj

    def _auto_discover_entrypoint(self) -> str:
        """Auto-discover entrypoint from config file.

        Returns:
            Path to the entrypoint

        Raises:
            ValueError: If no entrypoint found or multiple entrypoints exist
        """
        config_file = "uipath.json"
        if not os.path.isfile(config_file):
            raise ValueError(
                f"File '{config_file}' not found. Please run 'uipath init'."
            )

        with open(config_file, "r", encoding="utf-8") as f:
            uipath_config = json.loads(f.read())

        entrypoints = uipath_config.get("entryPoints", [])

        if not entrypoints:
            raise ValueError(
                "No entrypoints found in uipath.json. Please run 'uipath init'."
            )

        if len(entrypoints) > 1:
            entrypoint_paths = [ep.get("filePath") for ep in entrypoints]
            raise ValueError(
                f"Multiple entrypoints found: {entrypoint_paths}. "
                f"Please specify which entrypoint to use: uipath eval <entrypoint> [eval_set]"
            )

        entrypoint_path = entrypoints[0].get("filePath")

        console.info(
            f"Auto-discovered entrypoint: {click.style(entrypoint_path, fg='cyan')}"
        )
        return entrypoint_path

    def _auto_discover_eval_set(self) -> str:
        """Auto-discover evaluation set from evals/eval-sets directory.

        Returns:
            Path to the evaluation set file

        Raises:
            ValueError: If no eval set found or multiple eval sets exist
        """
        eval_sets_dir = Path("evals/eval-sets")

        if not eval_sets_dir.exists():
            raise ValueError(
                "No 'evals/eval-sets' directory found. "
                "Please set 'UIPATH_PROJECT_ID' env var and run 'uipath pull'."
            )

        eval_set_files = list(eval_sets_dir.glob("*.json"))

        if not eval_set_files:
            raise ValueError(
                "No evaluation set files found in 'evals/eval-sets' directory. "
            )

        if len(eval_set_files) > 1:
            file_names = [f.name for f in eval_set_files]
            raise ValueError(
                f"Multiple evaluation sets found: {file_names}. "
                f"Please specify which evaluation set to use: 'uipath eval [entrypoint] <eval_set_path>'"
            )

        eval_set_path = str(eval_set_files[0])
        console.info(
            f"Auto-discovered evaluation set: {click.style(eval_set_path, fg='cyan')}"
        )
        return eval_set_path

    def _initialize_results(self) -> None:
        """Initialize the results file and directory."""
        self._create_and_initialize_results_file()
        # Initialize progress reporter if needed
        if self._report_progress:
            agent_snapshot = self._extract_agent_snapshot()
            self._progress_reporter = ProgressReporter(
                eval_set_id=self._eval_set.id,
                agent_snapshot=agent_snapshot,
                no_of_evals=len(self._eval_set.evaluations),
                evaluators=self._evaluators,
            )

    def _extract_agent_snapshot(self) -> str:
        """Extract agent snapshot from uipath.json file.

        Returns:
            JSON string containing the agent snapshot with input and output schemas
        """
        config_file = "uipath.json"
        if not os.path.isfile(config_file):
            console.error(f"File '{config_file}' not found. Please run 'uipath init'")

        with open(config_file, "r", encoding="utf-8") as f:
            file_content = f.read()
        uipath_config = json.loads(file_content)

        entry_point = None
        for ep in uipath_config.get("entryPoints", []):
            if ep.get("filePath") == self.entrypoint:
                entry_point = ep
                break

        if not entry_point:
            console.error(
                f"No entry point found with filePath '{self.entrypoint}' in uipath.json"
            )

        input_schema = entry_point.get("input", {})  # type: ignore
        output_schema = entry_point.get("output", {})  # type: ignore

        # Format as agent snapshot
        agent_snapshot = {"inputSchema": input_schema, "outputSchema": output_schema}

        return json.dumps(agent_snapshot)

    def _create_and_initialize_results_file(self):
        # Create results directory if it doesn't exist
        results_dir = self.eval_set_path.parent.parent / "results"
        results_dir.mkdir(exist_ok=True)

        # Create results file
        timestamp = datetime.now(timezone.utc).strftime("%M-%H-%d-%m-%Y")
        eval_set_name = self._eval_set.name
        self.result_file = results_dir / f"eval-{eval_set_name}-{timestamp}.json"

        initial_results = EvaluationSetResult(
            eval_set_id=self._eval_set.id,
            eval_set_name=self._eval_set.name,
            results=[],
            average_score=0.0,
        )

        with open(self.result_file, "w", encoding="utf-8") as f:
            f.write(initial_results.model_dump_json(indent=2))

    def _load_eval_set(self, eval_ids: Optional[List[str]] = None) -> EvaluationSet:
        """Load the evaluation set from file.

        Returns:
            The loaded evaluation set as EvaluationSet model
        """
        with open(self.eval_set_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        eval_set = EvaluationSet(**data)
        if eval_ids:
            eval_set.extract_selected_evals(eval_ids)
        return eval_set

    def _load_evaluators(self) -> List[EvaluatorBase]:
        """Load evaluators referenced by the evaluation set."""
        evaluators = []
        evaluators_dir = self.eval_set_path.parent.parent / "evaluators"
        evaluator_refs = set(self._eval_set.evaluatorRefs)
        found_evaluator_ids = set()

        # Load evaluators from JSON files
        for file in evaluators_dir.glob("*.json"):
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                evaluator_id = data.get("id")

                if evaluator_id in evaluator_refs:
                    evaluator = EvaluatorFactory.create_evaluator(data)
                    evaluators.append(evaluator)
                    found_evaluator_ids.add(evaluator_id)

        # Check if all referenced evaluators were found
        missing_evaluators = evaluator_refs - found_evaluator_ids
        if missing_evaluators:
            raise ValueError(
                f"Could not find evaluators with IDs: {missing_evaluators}"
            )

        return evaluators

    async def _write_results(self, results: List[Any]) -> None:
        """Write evaluation results to file with async lock.

        Args:
            results: List of evaluation results to write
        """
        async with self._results_lock:
            # Read current results
            with open(self.result_file, "r", encoding="utf-8") as f:
                current_results = EvaluationSetResult.model_validate_json(f.read())

            # Add new results
            current_results.results.extend(results)

            if current_results.results:
                current_results.average_score = sum(
                    r.score for r in current_results.results
                ) / len(current_results.results)

            # Write updated results
            with open(self.result_file, "w", encoding="utf-8") as f:
                f.write(current_results.model_dump_json(indent=2))

    async def _results_queue_consumer(self, results_queue: asyncio.Queue[Any]) -> None:
        """Consumer task for the results queue that writes to local file.

        Args:
            results_queue: Queue containing evaluation results to write to file
        """
        while True:
            results: list[EvalItemResult] = await results_queue.get()
            if results is None:
                # Sentinel value - consumer should stop
                results_queue.task_done()
                return

            try:
                await self._write_results([eval_item.result for eval_item in results])
                results_queue.task_done()
            except Exception as e:
                console.warning(f"Error writing results to file: {str(e)}")
                results_queue.task_done()

    async def _sw_progress_reporter_queue_consumer(
        self, sw_progress_reporter_queue: asyncio.Queue[Any]
    ) -> None:
        """Consumer task for the SW progress reporter.

        Args:
            sw_progress_reporter_queue: Queue containing evaluation results to report to StudioWeb
        """
        while True:
            queue_item = await sw_progress_reporter_queue.get()
            if queue_item is None:
                # Sentinel value - consumer should stop
                sw_progress_reporter_queue.task_done()
                return
            eval_run_id: str
            eval_results: list[EvalItemResult]
            success: bool
            execution_time: float

            eval_run_id, eval_results, success, execution_time = queue_item

            try:
                if self._progress_reporter:
                    await self._progress_reporter.update_eval_run(
                        eval_results, eval_run_id, execution_time
                    )
                sw_progress_reporter_queue.task_done()
            except Exception as e:
                console.warning(f"Error reporting progress to StudioWeb: {str(e)}")
                sw_progress_reporter_queue.task_done()

    def _run_agent(self, input_json: str) -> tuple[Dict[str, Any], bool, float]:
        """Run the agent with the given input.

        Args:
            input_json: JSON string containing input data

        Returns:
            Agent output as dictionary and success status
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                import time

                output_file = Path(tmpdir) / "output.json"
                logs_file = Path(tmpdir) / "execution.log"

                # Suppress LangChain deprecation warnings during agent execution
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore", category=UserWarning, module="langchain"
                    )
                    # Note: Progress reporting is handled outside this method since it's async
                    start_time = time.time()
                    success, error_message, info_message = run_core(
                        entrypoint=self.entrypoint,
                        input=input_json,
                        resume=False,
                        input_file=None,
                        execution_output_file=output_file,
                        logs_file=logs_file,
                        runtime_dir=tmpdir,
                        is_eval_run=True,
                    )
                    execution_time = time.time() - start_time
                if not success:
                    console.warning(error_message)
                    return {}, False, execution_time
                else:
                    # Read the output file
                    with open(output_file, "r", encoding="utf-8") as f:
                        result = json.load(f)

                    # uncomment the following lines to have access to the execution.logs (needed for some types of evals)
                    # with open(logs_file, "r", encoding="utf-8") as f:
                    #     logs = f.read()
                    if isinstance(result, str):
                        try:
                            return json.loads(result), True, execution_time
                        except json.JSONDecodeError as e:
                            raise Exception(f"Error parsing output: {e}") from e
                return result, True, 0.0

            except Exception as e:
                console.warning(f"Error running agent: {str(e)}")
                return {"error": str(e)}, False, execution_time

    async def _process_evaluation(
        self,
        eval_item: Dict[str, Any],
        results_queue: asyncio.Queue[Any],
        sw_progress_reporter_queue: asyncio.Queue[Any],
    ) -> None:
        """Process a single evaluation item.

        Args:
            eval_item: The evaluation item to process
            results_queue: Queue for local file results
            sw_progress_reporter_queue: Queue for StudioWeb progress reporting
        """
        eval_id = eval_item["id"]
        eval_run_id: Optional[str] = None

        try:
            input_json = json.dumps(eval_item["inputs"])

            if self._report_progress and self._progress_reporter:
                eval_run_id = await self._progress_reporter.create_eval_run(eval_item)

            loop = asyncio.get_running_loop()
            actual_output, success, execution_time = await loop.run_in_executor(
                None,
                self._run_agent,
                input_json,
            )

            if success:
                # Run each evaluator
                eval_results: list[EvalItemResult] = []
                for evaluator in self._evaluators:
                    result = await evaluator.evaluate(
                        evaluation_id=eval_item["id"],
                        evaluation_name=eval_item["name"],
                        input_data=eval_item["inputs"],
                        expected_output=eval_item["expectedOutput"],
                        actual_output=actual_output,
                    )
                    eval_results.append(
                        EvalItemResult(evaluator_id=evaluator.id, result=result)
                    )

                await results_queue.put(eval_results)
                if self._report_progress:
                    # TODO: modify this, here we are only reporting for success
                    await sw_progress_reporter_queue.put(
                        (eval_run_id, eval_results, success, execution_time)
                    )

                # Update progress to completed
                if self._progress_manager:
                    self._progress_manager.complete_evaluation(eval_id)
            else:
                # Mark as failed if agent execution failed
                if self._progress_manager:
                    self._progress_manager.fail_evaluation(
                        eval_id, "Agent execution failed"
                    )

        except Exception as e:
            # Mark as failed with error message
            if self._progress_manager:
                self._progress_manager.fail_evaluation(eval_id, str(e))
            raise

    async def _producer_task(self, task_queue: asyncio.Queue[Any]) -> None:
        """Producer task that adds all evaluations to the queue.

        Args:
            task_queue: The asyncio queue to add tasks to
        """
        for eval_item in self._eval_set.evaluations:
            await task_queue.put(eval_item.model_dump())

        # Add sentinel values to signal workers to stop
        for _ in range(self._num_workers):
            await task_queue.put(None)

    async def _consumer_task(
        self,
        task_queue: asyncio.Queue[Any],
        worker_id: int,
        results_queue: asyncio.Queue[Any],
        sw_progress_reporter_queue: asyncio.Queue[Any],
    ) -> None:
        """Consumer task that processes evaluations from the queue.

        Args:
            task_queue: The asyncio queue to get tasks from
            worker_id: ID of this worker for logging
            results_queue: Queue for local file results
            sw_progress_reporter_queue: Queue for StudioWeb progress reporting
        """
        while True:
            eval_item = await task_queue.get()
            if eval_item is None:
                # Sentinel value - worker should stop
                task_queue.task_done()
                return

            try:
                await self._process_evaluation(
                    eval_item, results_queue, sw_progress_reporter_queue
                )
                task_queue.task_done()
            except Exception as e:
                # Log error and continue to next item
                task_queue.task_done()
                console.warning(
                    f"Evaluation {eval_item.get('name', 'Unknown')} failed: {str(e)}"
                )

    async def run_evaluation(self) -> None:
        """Run the evaluation set using multiple worker tasks."""
        console.info(
            f"Starting evaluating {click.style(self._eval_set.name, fg='cyan')} evaluation set..."
        )

        if self._report_progress and self._progress_reporter:
            await self._progress_reporter.create_eval_set_run()

        # Prepare items for progress tracker
        progress_items = [
            {"id": eval_item.id, "name": eval_item.name}
            for eval_item in self._eval_set.evaluations
        ]

        with console.evaluation_progress(progress_items) as progress_manager:
            self._progress_manager = progress_manager

            task_queue: asyncio.Queue[Any] = asyncio.Queue()
            results_queue: asyncio.Queue[Any] = asyncio.Queue()
            sw_progress_reporter_queue: asyncio.Queue[Any] = asyncio.Queue()

            producer = asyncio.create_task(self._producer_task(task_queue))

            consumers = []
            for worker_id in range(self._num_workers):
                consumer = asyncio.create_task(
                    self._consumer_task(
                        task_queue, worker_id, results_queue, sw_progress_reporter_queue
                    )
                )
                consumers.append(consumer)

            # Create results queue consumer
            results_consumer = asyncio.create_task(
                self._results_queue_consumer(results_queue)
            )

            # Create SW progress reporter queue consumer
            sw_progress_consumer = None
            if self._report_progress:
                sw_progress_consumer = asyncio.create_task(
                    self._sw_progress_reporter_queue_consumer(
                        sw_progress_reporter_queue
                    )
                )

            # Wait for producer to finish
            await producer
            await task_queue.join()

            # Wait for all consumers to finish
            await asyncio.gather(*consumers)

            # Signal queue consumers to stop by sending sentinel values
            await results_queue.put(None)
            if self._report_progress:
                await sw_progress_reporter_queue.put(None)

            await results_consumer
            if sw_progress_consumer:
                await sw_progress_consumer

            if self._progress_reporter:
                await self._progress_reporter.update_eval_set_run()

        console.info(f"Results saved to {click.style(self.result_file, fg='cyan')}")
