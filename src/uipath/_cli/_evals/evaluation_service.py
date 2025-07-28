import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
import uuid

from uipath._cli._utils._console import ConsoleLogger
from uipath._utils.constants import (
    ENV_PROJECT_ID,
    ENV_UIPATH_ACCESS_TOKEN,
    ENV_TENANT_ID
)

from ..cli_run import run
from .evaluators.llm_evaluator import LLMEvaluator
from .models import EvaluationSetResult

console = ConsoleLogger()

API_BASE_URL = "https://alpha.uipath.com/3334ab63-a329-483b-a046-4f2e5eee206f/dbcb040f-5a69-4043-b197-06b4f78e2820/agentsruntime_/api/execution/agents"

class EvaluationService:
    """Service for running evaluations."""

    def __init__(self, eval_set_path: str | Path):
        """Initialize the evaluation service.

        Args:
            eval_set_path: Path to the evaluation set file (can be string or Path)
        """
        self.eval_set_path = Path(eval_set_path)
        self.eval_set = self._load_eval_set()
        self.evaluators = self._load_evaluators()
        self.num_workers = 8
        self.results_lock = asyncio.Lock()
        self.eval_set_run_id = None  # Will be set after creating EvalSetRun
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

    def _load_evaluators(self) -> List[LLMEvaluator]:
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

    async def _create_eval_set_run(self) -> str:
        """Create an EvalSetRun in the database before starting evaluations.
        
        Returns:
            str: The evalSetRunId returned from the API
        """
        import os
        
        # Get required environment variables
        project_id = os.getenv(ENV_PROJECT_ID)
        access_token = os.getenv(ENV_UIPATH_ACCESS_TOKEN)
        tenant_id = os.getenv(ENV_TENANT_ID, "")
        
        if not project_id:
            raise Exception("UIPATH_PROJECT_ID environment variable is required")
        if not access_token:
            raise Exception("UIPATH_ACCESS_TOKEN environment variable is required")
        
        # Read agent schema from uipath.json
        agent_schema = self._get_agent_schema()
        
        # Construct API endpoint
        api_endpoint = f"{API_BASE_URL}/{project_id}/evalSetRun"
        
        # Prepare headers
        headers = {
            "accept": "*/*",
            "accept-language": "en-US,en;q=0.9",
            "authorization": f"Bearer {access_token}",
            "content-type": "application/json",
            "request-context": "appId=cid-v1:studio",
            "user-agent": "UiPath-Python-SDK-Evaluation"
        }
        
        # Add tenant ID header if available
        if tenant_id:
            headers["x-uipath-internal-tenantid"] = tenant_id
        
        # Prepare the request body
        # Convert evalSetId to UUID format if it's not already
        eval_set_id = self.eval_set["id"]
        try:
            # Try to parse as UUID to validate format
            uuid.UUID(eval_set_id)
        except ValueError:
            # If it's not a valid UUID, generate one
            console.warning(f"evalSetId '{eval_set_id}' is not a valid UUID, generating a new one")
            eval_set_id = str(uuid.uuid4())
        
        request_body = {
            "evalSetId": eval_set_id,
            "agentId": project_id,
            "agentSnapshot": {
                "inputSchema": agent_schema["input"],
                "outputSchema": agent_schema["output"],
                "tools": [],
                "contexts": [],
                "escalations": [],
                "systemPrompt": "You are a mathematical calculation assistant. Your task is to perform basic arithmetic operations on two given numbers.",
                "userPrompt": "Perform the following arithmetic operation:\\nFirst Number: {{first_number}}\\nSecond Number: {{second_number}}\\nOperation: addition\\n\\nPlease provide the result and a brief explanation of the calculation.",
                "settings": {
                    "model": "gpt-4o-2024-11-20",
                    "maxTokens": 16384,
                    "temperature": 0,
                    "engine": "basic-v1"
                }
            },
            "status": 1,
            "numberOfEvalsExecuted": len(self.eval_set["evaluations"])
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(api_endpoint, json=request_body, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                eval_set_run_id = result.get("id") or str(uuid.uuid4())
                
                console.info(f"Created EvalSetRun with ID: {eval_set_run_id}")
                return eval_set_run_id
                
        except Exception as e:
            console.warning(f"Failed to create EvalSetRun: {str(e)}")
            fallback_id = str(uuid.uuid4())
            console.info(f"Using fallback EvalSetRun ID: {fallback_id}")
            return fallback_id

    async def _create_eval_run(self, eval_item: Dict[str, Any]) -> Optional[str]:
        """Create an EvalRun for a single evaluation before it runs.
        
        Args:
            eval_item: The evaluation item to process
            
        Returns:
            The ID of the created EvalRun, or None if it failed.
        """
        import os
        
        # Get required environment variables
        project_id = os.getenv(ENV_PROJECT_ID)
        access_token = os.getenv(ENV_UIPATH_ACCESS_TOKEN)
        tenant_id = os.getenv(ENV_TENANT_ID, "")
        
        if not project_id or not access_token:
            console.warning("Missing environment variables for EvalRun API call")
            return None
        
        # Construct API endpoint
        api_endpoint = f"{API_BASE_URL}/{project_id}/evalRun"
        
        # Prepare headers
        headers = {
            "accept": "*/*",
            "authorization": f"Bearer {access_token}",
            "content-type": "application/json"
        }
        
        # Add tenant ID header if available
        if tenant_id:
            headers["x-uipath-internal-tenantid"] = tenant_id
        
        # Prepare assertion runs from evaluator definitions
        assertion_runs = []
        for evaluator in self.evaluators:
            # Create a rich assertionSnapshot from the evaluator's config
            assertion_properties = evaluator.config.copy()
            assertion_properties["expectedOutput"] = eval_item["expectedOutput"]

            assertion_run = {
                "assertionSnapshot": {
                    "assertionType": "Custom", # Align with the working example
                    "outputKey": "*",           # Align with the working example
                    "assertionProperties": assertion_properties
                },
                "status": 1, # Revert to integer status
                "evaluatorId": evaluator.config.get("id")
            }
            assertion_runs.append(assertion_run)
        
        # Prepare the request body
        request_body = {
            "evalSetRunId": self.eval_set_run_id,
            "evalSnapshot": {
                "id": eval_item["id"],
                "name": eval_item["name"],
                "assertionType": "Unknown", # Align with the working example
                "assertionProperties": {},    # Align with the working example
                "inputs": eval_item["inputs"],
                "outputKey": ""             # Align with the working example
            },
            "assertionRuns": assertion_runs,
            "status": 1 # Revert to integer status
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(api_endpoint, json=request_body, headers=headers)
                
                if response.status_code >= 400:
                    console.error(f"Failed to create EvalRun for {eval_item['name']}. Status: {response.status_code}, Body: {response.text}")
                    return None
                else:
                    result = response.json()
                    eval_run_id = result.get("id")
                    console.success(f"Successfully created EvalRun for {eval_item['name']} with ID: {eval_run_id}")
                    return eval_run_id
                    
        except Exception as e:
            console.warning(f"Failed to create EvalRun for {eval_item['name']}: {str(e)}")
            return None

    async def _update_eval_run(self, eval_run_id: str, actual_output: Any, eval_results: List[Any]) -> None:
        """Update an existing EvalRun with the results of an evaluation.
        
        Args:
            eval_run_id: The ID of the EvalRun to update.
            actual_output: The output from the agent.
            eval_results: The results from the evaluators.
        """
        import os

        # Get required environment variables
        project_id = os.getenv(ENV_PROJECT_ID)
        access_token = os.getenv(ENV_UIPATH_ACCESS_TOKEN)
        tenant_id = os.getenv(ENV_TENANT_ID, "")

        if not project_id or not access_token:
            console.warning("Missing environment variables for EvalRun update API call")
            return

        # Construct API endpoint
        api_endpoint = f"{API_BASE_URL}/{project_id}/evalRun"

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        if tenant_id:
            headers["x-uipath-internal-tenantid"] = tenant_id

        # Prepare evaluator scores and assertion runs
        evaluator_scores = []
        assertion_runs = []
        overall_status = 2  # Default to Success

        for result in eval_results:
            score_status = 2 if result.score >= 70 else 3 # 2=Success, 3=Failure
            if score_status == 3:
                overall_status = 3 # If any evaluator fails, the run fails

            evaluator_scores.append({
                "Type": 1,
                "Value": result.score,
                "Justification": result.details,
                "EvaluatorId": result.evaluator_id,
            })
            assertion_runs.append({
                "Status": score_status,
                "EvaluatorId": result.evaluator_id,
                "Result": {
                    "Output": {"reasoning": result.details, "passed": score_status == 2},
                    "Score": {"Type": 1, "Value": result.score, "Justification": result.details}
                },
                "CompletionMetrics": {"Duration": 1200, "Tokens": 75, "CompletionTokens": 35, "PromptTokens": 40} # Placeholder
            })

        # Prepare the request body
        request_body = {
            "EvalRunId": eval_run_id,
            "Status": overall_status,
            "Result": {
                "Output": {"output": actual_output} if isinstance(actual_output, str) else actual_output,
                "EvaluatorScores": evaluator_scores
            },
            "CompletionMetrics": {"Duration": 2500, "Tokens": 150, "CompletionTokens": 75, "PromptTokens": 75}, # Placeholder
            "AssertionRuns": assertion_runs
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(api_endpoint, json=request_body, headers=headers)

                if response.status_code >= 400:
                    console.error(f"Failed to update EvalRun for ID {eval_run_id}. Status: {response.status_code}, Body: {response.text}")
                else:
                    console.success(f"Successfully updated EvalRun with ID: {eval_run_id}")
        except Exception as e:
            console.warning(f"An exception occurred while updating EvalRun with ID {eval_run_id}: {str(e)}")

    async def _update_eval_set_run(self, final_results: EvaluationSetResult) -> None:
        """Update the EvalSetRun with the final, aggregated results.
        
        Args:
            final_results: The final results object containing all evaluation outcomes.
        """
        import os

        # Get required environment variables
        project_id = os.getenv(ENV_PROJECT_ID)
        access_token = os.getenv(ENV_UIPATH_ACCESS_TOKEN)
        tenant_id = os.getenv(ENV_TENANT_ID, "")

        if not project_id or not access_token or not self.eval_set_run_id:
            console.warning("Missing data for EvalSetRun update API call; skipping.")
            return

        # Construct API endpoint
        api_endpoint = f"{API_BASE_URL}/{project_id}/evalSetRun"

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
        }
        if tenant_id:
            headers["x-uipath-internal-tenantid"] = tenant_id
        
        # Aggregate evaluator scores
        evaluator_scores = []
        for result in final_results.results:
            evaluator_scores.append({
                "value": result.score,
                "evaluatorId": result.evaluator_id
            })

        # Prepare the request body
        request_body = {
            "EvalSetRunId": self.eval_set_run_id,
            "status": 2,  # 2 = Completed
            "score": final_results.average_score,
            "evaluatorScores": evaluator_scores
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.put(api_endpoint, json=request_body, headers=headers)

            if response.status_code >= 400:
                console.error(f"Failed to update EvalSetRun with ID {self.eval_set_run_id}. Status: {response.status_code}, Body: {response.text}")
            else:
                console.success(f"Successfully updated EvalSetRun with ID: {self.eval_set_run_id}")
        except Exception as e:
            console.warning(f"An exception occurred while updating EvalSetRun: {str(e)}")

    def _get_agent_schema(self) -> Dict[str, Any]:
        """Get agent input/output schema from uipath.json.
        
        Returns:
            Dict containing input and output schemas
        """
        try:
            import os
            import json
            if os.path.exists("uipath.json"):
                with open("uipath.json", "r") as f:
                    config = json.load(f)
                    entry_points = config.get("entryPoints", [])
                    if entry_points:
                        return {
                            "input": entry_points[0].get("input", {}),
                            "output": entry_points[0].get("output", {})
                        }
        except Exception as e:
            console.warning(f"Could not read agent schema: {str(e)}")
        
        # Fallback schema based on our math agent
        return {
            "input": {
                "type": "object",
                "properties": {
                    "first_number": {
                        "type": "integer",
                        "description": "The first number for the arithmetic operation"
                    },
                    "second_number": {
                        "type": "integer", 
                        "description": "The second number for the arithmetic operation"
                    }
                },
                "required": ["first_number", "second_number"]
            },
            "output": {
                "type": "object",
                "description": "The formatted result of the arithmetic operation"
            }
        }

    def _run_agent(self, input_json: str) -> Dict[str, Any]:
        """Run the agent with the given input.

        Args:
            input_json: JSON string containing input data

        Returns:
            Agent output as dictionary
        """
        try:
            # Read entrypoint from uipath.json
            import json
            import os
            import subprocess
            import sys
            
            entrypoint = None
            if os.path.exists("uipath.json"):
                with open("uipath.json", "r") as f:
                    config = json.load(f)
                    entry_points = config.get("entryPoints", [])
                    if entry_points:
                        entrypoint = entry_points[0].get("filePath")
            
            if not entrypoint:
                raise Exception("No entrypoint found in uipath.json")
            
            # Run the agent using subprocess to avoid event loop conflicts
            cmd = ["uipath", "run", entrypoint, input_json]
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
            
            if result.returncode != 0:
                raise Exception(f"Agent execution failed: {result.stderr}")
            
            # Parse the output from the stdout
            # The CLI prints the result as a dictionary representation
            output_lines = result.stdout.strip().split('\n')
            
            # Find the line with the actual output (should be a dict representation)
            for line in output_lines:
                if line.startswith("{'") or line.startswith('{"'):
                    # This is likely our output
                    try:
                        # The output is in format like {'str': 'Math Agent Calculation:...'}
                        # We need to extract the actual string content
                        if line.startswith("{'str': '") and line.endswith("'}"):
                            # Extract the string content
                            content = line[8:-2]  # Remove {'str': ' and '}
                            # Unescape the content
                            content = content.replace('\\n', '\n')
                            return content
                        else:
                            # Try to evaluate it as a dict
                            import ast
                            output_dict = ast.literal_eval(line)
                            if isinstance(output_dict, dict) and 'str' in output_dict:
                                return output_dict['str']
                            return output_dict
                    except Exception as e:
                        console.warning(f"Could not parse output line: {line}, error: {e}")
                        continue
            
            # If we couldn't parse the structured output, return the raw stdout
            return {"raw_output": result.stdout.strip()}

        except Exception as e:
            console.error(f"Error running agent: {str(e)}")
            return {"error": str(e)}

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
        actual_output = await loop.run_in_executor(None, self._run_agent, input_json)

        # Run each evaluator
        eval_results = []
        for evaluator in self.evaluators:
            result = await evaluator.evaluate(
                evaluation_id=eval_item["id"],
                evaluation_name=eval_item["name"],
                input_data=eval_item["inputs"],
                expected_output=eval_item["expectedOutput"],
                actual_output={"output": actual_output} if isinstance(actual_output, str) else actual_output,
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
                # Log error and continue to next item
                task_queue.task_done()
                console.warning(
                    f"Worker {worker_id} failed evaluation {eval_item.get('name', 'Unknown')}: {str(e)}"
                )

    async def run_evaluation(self) -> None:
        """Run the evaluation set sequentially."""
        import os
        console.info(f"Starting evaluation of {len(self.eval_set['evaluations'])} test cases...")
        
        # Create EvalSetRun
        self.eval_set_run_id = await self._create_eval_set_run()

        for eval_item in self.eval_set["evaluations"]:
            try:
                console.info(f"----- Starting Evaluation: {eval_item['name']} -----")

                # 1. Create the EvalRun first
                eval_run_id = await self._create_eval_run(eval_item)
                
                if not eval_run_id:
                    console.warning(f"Skipping evaluation {eval_item['name']} due to failed EvalRun creation.")
                    continue

                # 2. Run the agent locally
                input_json = json.dumps(eval_item["inputs"])
                
                console.info(f"Executing agent with input: {input_json}")
                try:
                    actual_output = self._run_agent(input_json)
                    console.info(f"Agent raw output: {actual_output}")
                except Exception as e:
                    console.error(f"Agent execution failed: {str(e)}")
                    actual_output = {"error": str(e)}

                # 3. Score the results with LLM evaluators
                eval_results = []
                for evaluator in self.evaluators:
                    # Handle the new expectedOutput format with content field
                    expected_output = eval_item["expectedOutput"]
                    if isinstance(expected_output, dict) and "content" in expected_output:
                        expected_output = {"output": expected_output["content"]}
                    elif isinstance(expected_output, str):
                        expected_output = {"output": expected_output}
                    
                    result = await evaluator.evaluate(
                        evaluation_id=eval_item["id"],
                        evaluation_name=eval_item["name"],
                        input_data=eval_item["inputs"],
                        expected_output=expected_output,
                        actual_output={"output": actual_output} if isinstance(actual_output, str) else actual_output,
                    )
                    eval_results.append(result)
                    console.info(f"LLM Evaluation Score: {result.score}/100 - {result.details}")

                # 4. Write final results to local file
                await self._write_results(eval_results)

                # 5. Update the EvalRun with the results
                if eval_run_id:
                    await self._update_eval_run(eval_run_id, actual_output, eval_results)
                
                console.info(f"----- Finished Evaluation: {eval_item['name']} -----\n")
                
            except Exception as e:
                console.warning(f"Failed evaluation {eval_item.get('name', 'Unknown')}: {str(e)}")

        # After all evaluations are processed, update the EvalSetRun with final results
        if os.path.exists(self.result_file):
            final_results = EvaluationSetResult.model_validate_json(open(self.result_file, "r").read())
            await self._update_eval_set_run(final_results)

        console.success(f"All evaluations complete. Results saved to {self.result_file}")
