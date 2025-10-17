from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder
from ..models.guardrails import (
    AgentEscalationRecipient,
    BlockAction,
    BuiltInValidatorGuardrail,
    CustomGuardrail,
    EnumListParameterValue,
    EscalateAction,
    EscalateActionApp,
    FilterAction,
    Guardrail,
    GuardrailAction,
    GuardrailSelector,
    LogAction,
    MapEnumParameterValue,
    NumberParameterValue,
    ValidatorParameter,
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
            raise NotImplementedError("Custom guardrail validation is not yet supported by the API.")

    @traced
    def execute_guardrail(
        self,
        validation_result: Dict[str, Any],
        guardrail: Guardrail,
    ) -> None:
        """
        Execute the action specified by the guardrail if validation failed.
        Raise, log, escalate, or print, depending on action type.
        """
        if validation_result.get("validation_passed", True):
            return

        action = guardrail.action

        if isinstance(action, EscalateAction):
            # TODO fa o aplicatie in studio + review vezi ce se intmapla

            const requiredEscalationAppInputs = [
                "GuardrailName",
                "GuardrailDescription",
                "TenantName",
                "AgentTrace",
                "Tool",
                "ExecutionStage",
                "ToolInputs",
                "ToolOutputs",
            ]

            const requiredEscalationAppOutputs = ["ReviewedInputs", "ReviewedOutputs", "Reason"]

            const requiredEscalationAppOutcomes = ["Approve", "Reject"]

            # interrupt
            # create task/action
            # user clicks ..
            # resume
        elif isinstance(action, BlockAction):
            raise GuardrailViolationError(action.reason)
        elif isinstance(action, LogAction):
            reason = validation_result.get("reason", "Guardrail violation detected")
            severity = action.severity_level.value
            print(f"GUARDRAIL LOG [{severity}]: {reason}")
        elif isinstance(action, FilterAction):
            print(f"GUARDRAIL FILTER: Fields to filter: {[f.path for f in action.fields]}")
