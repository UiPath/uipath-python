import asyncio
import json
import tempfile
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List

from uipath._cli._utils._console import ConsoleLogger

from ..cli_run import run_core
from .evaluators.evaluator_base import EvaluatorBase
from .evaluators.llm_evaluator import LLMEvaluator
from .models import EvaluationSetResult

console = ConsoleLogger()


class EvaluationService:
    """Service for running evaluations."""

    def __init__(self, entrypoint: str, eval_set_path: str | Path, workers: int):
        """Initialize the evaluation service.

        Args:
            eval_set_path: Path to the evaluation set file (can be string or Path)
        """
        self.entrypoint = entrypoint
        self.eval_set_path = Path(eval_set_path)
        self.eval_set = self._load_eval_set()
        self.evaluators = self._load_evaluators()
        self.num_workers = workers
        self.results_lock = asyncio.Lock()
        self._initialize_results()

    def _initialize_results(self) -> None:
        """Initialize the results file and directory."""
        # Create results directory if it doesn't exist
        results_dir = self.eval_set_path.parent.parent / "results"
        results_dir.mkdir(exist_ok=True)

        # Create results file
        timestamp = datetime.now(UTC).strftime("%M-%H-%d-%m-%Y")
        eval_set_name = self.eval_set["name"]
        self.result_file = results_dir / f"eval-{eval_set_name}-{timestamp}.json"

        # Initialize with empty results
        initial_results = EvaluationSetResult(
            eval_set_id=self.eval_set["id"],
            eval_set_name=self.eval_set["name"],
            results=[],
            average_score=0.0,
        )

        with open(self.result_file, "w", encoding="utf-8") as f:
            f.write(initial_results.model_dump_json(indent=2))

    def _load_eval_set(self) -> Dict[str, Any]:
        """Load the evaluation set from file.

        Returns:
            The loaded evaluation set
        """
        with open(self.eval_set_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_evaluators(self) -> List[EvaluatorBase]:
        """Load evaluators referenced by the evaluation set."""
        evaluators = []
        evaluators_dir = self.eval_set_path.parent.parent / "evaluators"

        for evaluator_id in self.eval_set["evaluatorRefs"]:
            # Find evaluator file
            evaluator_file = None
            for file in evaluators_dir.glob("*.json"):
                with open(file) as f:
                    data = json.load(f)
                    if data.get("id") == evaluator_id:
                        evaluator_file = data
                        break

            if not evaluator_file:
                raise ValueError(f"Could not find evaluator with ID {evaluator_id}")

            evaluators.append(LLMEvaluator(evaluator_file))

        return evaluators

    async def _write_results(self, results: List[Any]) -> None:
        """Write evaluation results to file with async lock.

        Args:
            results: List of evaluation results to write
        """
        async with self.results_lock:
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

    def _run_agent(self, input_json: str) -> tuple[Dict[str, Any], bool]:
        """Run the agent with the given input.

        Args:
            input_json: JSON string containing input data

        Returns:
            Agent output as dictionary
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                output_file = Path(tmpdir) / "output.json"
                logs_file = Path(tmpdir) / "execution.log"

                # Suppress LangChain deprecation warnings during agent execution
                with warnings.catch_warnings():
                    warnings.filterwarnings(
                        "ignore", category=UserWarning, module="langchain"
                    )
                    success, error_message, info_message = run_core(
                        entrypoint=self.entrypoint,
                        input=input_json,
                        resume=False,
                        input_file=None,
                        execution_output_file=output_file,
                        logs_file=logs_file,
                        runtime_dir=tmpdir,
                        eval_run=True,
                    )
                if not success:
                    console.warning(error_message)
                    return {}, False
                else:
                    # Read the output file
                    with open(output_file, "r", encoding="utf-8") as f:
                        result = json.load(f)

                    # uncomment the following lines to have access to the execution.logs (needed for some types of evals)
                    # with open(logs_file, "r", encoding="utf-8") as f:
                    #     logs = f.read()
                    if isinstance(result, str):
                        try:
                            return json.loads(result), True
                        except json.JSONDecodeError as e:
                            raise Exception(f"Error parsing output: {e}") from e
                return result, True

            except Exception as e:
                console.warning(f"Error running agent: {str(e)}")
                return {"error": str(e)}, False

    async def _process_evaluation(self, eval_item: Dict[str, Any]) -> None:
        """Process a single evaluation item.

        Args:
            eval_item: The evaluation item to process
        """
        console.info(f"Running evaluation: {eval_item['name']}")

        # Run the agent using the evaluation input
        input_json = json.dumps(eval_item["inputs"])

        # Run _run_agent in a non-async context using run_in_executor
        loop = asyncio.get_running_loop()
        actual_output, success = await loop.run_in_executor(
            None, self._run_agent, input_json
        )
        if success:
            # Run each evaluator
            eval_results = []
            for evaluator in self.evaluators:
                result = await evaluator.evaluate(
                    evaluation_id=eval_item["id"],
                    evaluation_name=eval_item["name"],
                    input_data=eval_item["inputs"],
                    expected_output=eval_item["expectedOutput"],
                    actual_output=actual_output,
                )
                eval_results.append(result)

            # Write results immediately
            await self._write_results(eval_results)

        # TODO: here we should send the event to the SW eval API
        console.info(f"Evaluation {eval_item['name']} complete.")

    async def _producer_task(self, task_queue: asyncio.Queue) -> None:
        """Producer task that adds all evaluations to the queue.

        Args:
            task_queue: The asyncio queue to add tasks to
        """
        for eval_item in self.eval_set["evaluations"]:
            await task_queue.put(eval_item)

        # Add sentinel values to signal workers to stop
        for _ in range(self.num_workers):
            await task_queue.put(None)

    async def _consumer_task(self, task_queue: asyncio.Queue, worker_id: int) -> None:
        """Consumer task that processes evaluations from the queue.

        Args:
            task_queue: The asyncio queue to get tasks from
            worker_id: ID of this worker for logging
        """
        while True:
            eval_item = await task_queue.get()
            if eval_item is None:
                # Sentinel value - worker should stop
                task_queue.task_done()
                return

            try:
                await self._process_evaluation(eval_item)
                task_queue.task_done()
            except Exception as e:
                import click

                # Log error and continue to next item
                task_queue.task_done()
                console.warning(
                    f"Worker {worker_id} failed evaluation {eval_item.get('name', 'Unknown')}: {str(e)}"
                )

    async def run_evaluation(self) -> None:
        """Run the evaluation set using multiple worker tasks."""
        task_queue = asyncio.Queue()

        producer = asyncio.create_task(self._producer_task(task_queue))

        consumers = []
        for worker_id in range(self.num_workers):
            consumer = asyncio.create_task(self._consumer_task(task_queue, worker_id))
            consumers.append(consumer)

        await producer

        await task_queue.join()

        # Wait for all consumers to finish
        await asyncio.gather(*consumers)

        console.success(
            f"All evaluations complete. Results saved to {self.result_file}"
        )
