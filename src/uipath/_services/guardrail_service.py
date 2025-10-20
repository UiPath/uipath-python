from enum import Enum
from typing import Any, Dict, Optional, Union

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
