from enum import Enum
from typing import Any, Dict, List, Optional, Union

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder
from ..models import CreateAction
from ..models.guardrails import (
    BlockAction,
    BuiltInValidatorGuardrail,
    EscalateAction,
    FilterAction,
    Guardrail,
    LogAction,
)
from ..tracing import traced
from ._base_service import BaseService


class GuardrailResult(Enum):
    APPROVE = "approve"
    REJECT = "reject"


class GuardrailViolationError(Exception):
    """Exception raised when guardrail validation fails."""

    def __init__(self, detected_issue: Any):
        self.detected_issue = detected_issue
        super().__init__(f"Guardrail violation detected: {detected_issue}")


class GuardrailsService(FolderContext, BaseService):
    """Service for validating text against UiPath Guardrails."""

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced("evaluate_guardrail", run_type="uipath")
    def evaluate_guardrail(
        self,
        input_data: Union[str, Dict[str, Any]],
        guardrail: Guardrail,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call the API to validate input_data with the given guardrail.

        Only supports built-in guardrails for now.
        """
        if isinstance(guardrail, BuiltInValidatorGuardrail):
            parameters = [
                param.model_dump(by_alias=True)
                for param in guardrail.validator_parameters
            ]
            payload = {
                "validator": guardrail.validator_type,
                "input": input_data if isinstance(input_data, str) else str(input_data),
                "parameters": parameters,
            }
            spec = RequestSpec(
                method="POST",
                endpoint=Endpoint("/agentsruntime_/api/execution/guardrails/validate"),
                json=payload,
                headers={**header_folder(folder_key, folder_path)},
            )
            response = self.request(
                spec.method,
                url=spec.endpoint,
                json=spec.json,
                headers=spec.headers,
            )
            return response.json()
        else:
            raise NotImplementedError(
                "Custom guardrail validation is not yet supported by the API."
            )

    @traced("execute_guardrail", run_type="uipath")
    async def execute_guardrail(
        self,
        validation_result: Dict[str, Any],
        guardrail: Guardrail,
        tool_name: str,
    ) -> None:
        """Execute the action specified by the guardrail if validation failed.

        Raise, log, escalate, or print, depending on action type.
        """
        if validation_result.get("validation_passed", True):
            return

        action = guardrail.action

        if isinstance(action, EscalateAction):
            from uipath._cli._runtime._hitl import HitlProcessor, HitlReader

            action_data = {
                "GuardrailName": guardrail.name,
                "GuardrailDescription": validation_result.get(
                    "reason", "No description provided"
                ),
                # TODO must see where to i extract these
                # "TenantName": self.config.tenant_name,
                # "AgentTrace": must see,
                "Tool": tool_name,
                # "ExecutionStage": validation_result.get("execution_stage", ""),
                # "ToolInputs": ,
                # "ToolOutputs": validation_result.get("tool_outputs", {}),
            }
            # mandatory: app_name + tittle + data + app_version + assignee (def none) + appfolderpath + includemetadata = true
            create_action = CreateAction(
                title="Guardrail Escalation: " + guardrail.name,
                data=action_data,
                assignee=action.recipient.value,
                app_name=action.app.name,
                app_folder_path=action.app.folder_name,
                app_folder_key=action.app.folder_id,
                app_key=action.app.id,
                app_version=action.app.version,
                include_metadata=True,
            )
            # action_output = interrupt(create_action)
            print("Starting escalation action")
            processor = HitlProcessor(create_action)
            print(f"processor: {processor}")
            resume_trigger = await processor.create_resume_trigger()
            print(f"resume_trigger: {resume_trigger}")
            action_output = await HitlReader.read(resume_trigger)
            print(f"action_output: {action_output}")
            print("Escalation action completed.")

            if action_output:
                if hasattr(action_output, "action") and hasattr(action_output, "data"):
                    if action_output.action == "Approve":
                        if action_output.data and action_output.data.get(
                            "ReviewedInputs"
                        ):
                            # Re-evaluate with reviewed inputs
                            self.evaluate_guardrail(
                                input_data=action_output.data["ReviewedInputs"],
                                guardrail=guardrail,
                                folder_key=action.app.folder_id,
                                folder_path=action.app.folder_name,
                            )
                        return
                    elif action_output.action == "Reject":
                        reason = "Guardrail violation rejected by user"
                        if hasattr(action_output, "data") and action_output.data:
                            reason = action_output.data.get("Reason", reason)
                        raise GuardrailViolationError(reason)

        elif isinstance(action, BlockAction):
            raise GuardrailViolationError(action.reason)
        elif isinstance(action, LogAction):
            reason = validation_result.get("reason", "Guardrail violation detected")
            severity = action.severity_level.value
            print(f"GUARDRAIL LOG [{severity}]: {reason}")

        elif isinstance(action, FilterAction):
            # TODO: see what it clearly does
            # implement filtering logic
            print(
                f"GUARDRAIL FILTER: Fields to filter: {[f.path for f in action.fields]}"
            )

    def _should_apply_guardrail(self, guardrail: Guardrail, tool_name: str) -> bool:
        """Check if guardrail should apply to the current tool context."""
        selector = guardrail.selector

        # Check scopes
        scope_values = [scope.value for scope in selector.scopes]
        if "Tool" not in scope_values:
            return False

        # Check match names (if specified)
        if selector.match_names:
            return tool_name in selector.match_names or "*" in selector.match_names

        return True

    @traced("process_guardrails", run_type="uipath")
    async def process_guardrails(
        self,
        input_data: Union[str, Dict[str, Any]],
        guardrails: List[Guardrail],
        tool_name: str = "unknown",
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
        stop_on_first_failure: bool = True,
    ) -> Dict[str, Any]:
        """Process multiple guardrails: evaluate each one and execute its action if needed.

        Args:
            input_data: Data to validate
            guardrails: List of guardrails to process
            tool_name: Name of the tool being validated
            folder_key: Optional folder key
            folder_path: Optional folder path
            stop_on_first_failure: Whether to stop processing on first failure

        Returns:
            Summary of processing results
        """
        results: Dict[str, Any] = {
            "input_data": str(input_data),
            "tool_name": tool_name,
            "total_guardrails": len(guardrails),
            "processed": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "errors": 0,
            "all_passed": True,
            "details": [],
        }

        print(f"Processing {len(guardrails)} guardrail(s) for tool '{tool_name}'")

        for i, guardrail in enumerate(guardrails):
            detail: Dict[str, Any] = {
                "guardrail_id": guardrail.id,
                "guardrail_name": guardrail.name,
                "guardrail_type": guardrail.guardrail_type,
                "index": i + 1,
            }

            try:
                # Check if guardrail should apply to this tool
                if not self._should_apply_guardrail(guardrail, tool_name):
                    detail.update(
                        {
                            "status": "skipped",
                            "reason": "Guardrail does not apply to this tool",
                        }
                    )
                    results["details"].append(detail)
                    results["skipped"] = results["skipped"] + 1
                    continue

                # Evaluate the guardrail
                validation_result = self.evaluate_guardrail(
                    input_data=input_data,
                    guardrail=guardrail,
                    folder_key=folder_key,
                    folder_path=folder_path,
                )

                results["processed"] = results["processed"] + 1

                # Check if validation passed
                if validation_result.get("validation_passed", True):
                    detail.update(
                        {"status": "passed", "validation_result": validation_result}
                    )
                    results["details"].append(detail)
                    results["passed"] = results["passed"] + 1
                else:
                    # Execute the guardrail action
                    await self.execute_guardrail(
                        validation_result=validation_result,
                        guardrail=guardrail,
                        tool_name=tool_name,
                    )

                    detail.update(
                        {
                            "status": "failed_but_handled",
                            "validation_result": validation_result,
                        }
                    )
                    results["details"].append(detail)
                    results["failed"] = results["failed"] + 1
                    results["all_passed"] = False

            except GuardrailViolationError as e:
                detail.update({"status": "blocked", "error": str(e)})
                results["details"].append(detail)
                results["failed"] = results["failed"] + 1
                results["all_passed"] = False

                if stop_on_first_failure:
                    print(f"Stopping on first failure: {e}")
                    raise
                else:
                    print(f"Guardrail violation (continuing): {e}")

            except Exception as e:
                detail.update({"status": "error", "error": str(e)})
                results["details"].append(detail)
                results["errors"] = results["errors"] + 1
                results["all_passed"] = False
                print(f"Error processing guardrail '{guardrail.name}': {e}")

        # Summary
        print("  Processing Summary:")
        print(f"  Total: {results['total_guardrails']}")
        print(f"  Processed: {results['processed']}")
        print(f"  Passed: {results['passed']}")
        print(f"  Failed: {results['failed']}")
        print(f"  Skipped: {results['skipped']}")
        print(f"  Errors: {results['errors']}")
        print(f"  All passed: {results['all_passed']}")

        return results
