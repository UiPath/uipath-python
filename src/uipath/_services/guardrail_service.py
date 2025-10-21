from enum import Enum
from typing import Any, Dict, List, Optional, Union

from uipath._cli._runtime._hitl import HitlProcessor, HitlReader

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

    @traced
    def evaluate_guardrail(
        self,
        input_data: Union[str, Dict[str, Any]],
        guardrail: Guardrail,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Call the API to validate input_data with the given guardrail.
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

    @traced
    async def execute_guardrail(
        self,
        validation_result: Dict[str, Any],
        guardrail: Guardrail,
        tool_name: str,
    ) -> None:
        """
        Execute the action specified by the guardrail if validation failed.
        Raise, log, escalate, or print, depending on action type.
        """
        if validation_result.get("validation_passed", True):
            return

        action = guardrail.action

        if isinstance(action, EscalateAction):
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

            # nu merge asta
            # action_output = interrupt(create_action)
            processor = HitlProcessor(create_action)
            resume_trigger = await processor.create_resume_trigger()
            action_output = await HitlReader.read(resume_trigger)

            if hasattr(action_output, "action"):
                if action_output.action == "Approve":
                    if hasattr(action_output, "data") and action_output.data.get(
                        "ReviewedInputs"
                    ):
                        # Re-evaluate with reviewed inputs
                        await self.evaluate_guardrail(
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

    @traced
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
        """
        Process multiple guardrails: evaluate each one and execute its action if needed.

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
        results = {
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
            detail = {
                "guardrail_id": guardrail.id,
                "guardrail_name": guardrail.name,
                "guardrail_type": guardrail.guardrail_type,
                "index": i + 1,
            }

            try:
                print(f"[{i + 1}/{len(guardrails)}] {guardrail.name}")

                # Check if guardrail applies to this context
                if not self._should_apply_guardrail(guardrail, tool_name):
                    results["skipped"] += 1
                    detail.update(
                        {"status": "skipped", "reason": "Scope or name mismatch"}
                    )
                    results["details"].append(detail)
                    continue

                # 1: Evaluate guardrail
                validation_result = self.evaluate_guardrail(
                    input_data=input_data,
                    guardrail=guardrail,
                    folder_key=folder_key,
                    folder_path=folder_path,
                )

                results["processed"] += 1
                validation_passed = validation_result.get("validation_passed", True)

                if validation_passed:
                    results["passed"] += 1
                    detail.update(
                        {"status": "passed", "validation_result": validation_result}
                    )
                else:
                    results["failed"] += 1
                    results["all_passed"] = False
                    reason = validation_result.get("reason", "Unknown reason")

                    detail.update(
                        {
                            "status": "failed",
                            "reason": reason,
                            "validation_result": validation_result,
                        }
                    )

                    # 2: Execute guardrail action
                    try:
                        await self.execute_guardrail(
                            validation_result=validation_result,
                            guardrail=guardrail,
                            tool_name=tool_name,
                        )
                        detail["action_executed"] = True

                    except GuardrailViolationError:
                        detail["action_executed"] = True
                        detail["blocked"] = True
                        raise

                    except Exception as action_error:
                        detail["action_error"] = str(action_error)
                        print(f"Action execution failed: {action_error}")

                    # Stop on first failure if requested
                    if stop_on_first_failure:
                        detail["stopped_early"] = True
                        results["details"].append(detail)
                        break

                results["details"].append(detail)

            except GuardrailViolationError:
                detail["status"] = "blocked"
                results["details"].append(detail)
                raise

            except Exception as e:
                results["errors"] += 1
                results["all_passed"] = False
                detail.update({"status": "error", "error": str(e)})
                results["details"].append(detail)

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
