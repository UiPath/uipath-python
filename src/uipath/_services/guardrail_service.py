from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder
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


@dataclass
class GuardrailActionApp:
    """Configuration for the app used in guardrail actions."""

    name: str
    version: str
    folderName: str
    return_all_action: bool = False


@dataclass
class GuardrailActionRecipient:
    """Configuration for the recipient of guardrail actions."""

    displayName: str
    email: Optional[str] = None


@dataclass
class GuardrailAction:
    """Configuration for actions to take when guardrails are triggered."""

    actionType: str
    app: GuardrailActionApp
    recipient: GuardrailActionRecipient


@dataclass
class GuardrailSelector:
    """Selector configuration for determining when guardrails apply."""

    scopes: List[str]
    matchNames: List[str]


@dataclass
class RuleParameter:
    """Parameter configuration for guardrail rules."""

    parameterType: str
    value: Any
    id: str


@dataclass
class GuardrailRule:
    """Configuration for individual guardrail validation rules."""

    ruleType: str
    validator: str
    parameters: List[RuleParameter]


@dataclass
class GuardrailPolicy:
    """Complete guardrail policy configuration."""

    name: str
    description: str
    rules: List[GuardrailRule]
    action: GuardrailAction
    enabledForEvals: bool
    selector: GuardrailSelector


class GuardrailsService(FolderContext, BaseService):
    """Service for validating text against UiPath Guardrails."""

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def _call_validator(
        self,
        validator_name: str,
        input_text: str,
        parameters: List[Dict[str, Any]],
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> GuardrailResult:
        spec = self._validate_spec(
            validator_name=validator_name,
            input_text=input_text,
            parameters=parameters,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        )

        response_data = response.json()
        validation_passed = response_data.get("validation_passed", False)

        if validation_passed:
            return GuardrailResult.APPROVE
        else:
            return GuardrailResult.REJECT

    def _validate_spec(
        self,
        validator_name: str,
        input_text: str,
        parameters: List[Dict[str, Any]],
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        payload = {
            "validator": validator_name,
            "input": input_text,
            "parameters": parameters or [],
        }

        return RequestSpec(
            method="POST",
            endpoint=Endpoint("/agentsruntime_/api/execution/guardrails/validate"),
            json=payload,
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    @traced(name="guardrails_get_definitions", run_type="uipath")
    def get_definitions(
        self,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get available guardrail validator definitions from the API."""
        response = self.request(
            "GET",
            url=Endpoint("/agentsruntime_/api/execution/guardrails/definitions"),
            headers={
                **header_folder(folder_key, folder_path),
            },
        )
        return response.json()

    @traced(name="guardrails_pii_detection", run_type="uipath")
    def pii_detection(
        self,
        input_text: str,
        *,
        entities: Optional[List[str]] = None,
        entity_thresholds: Optional[Dict[str, float]] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> GuardrailResult:
        """Detect PII entities in input text.

        Args:
            input_text: The text to validate
            entities: List of PII entity types to detect (e.g., ["Email"])
            entity_thresholds: Confidence thresholds for each entity type
            folder_key: Optional folder key for context
            folder_path: Optional folder path for context

        Returns:
            GuardrailResult indicating validation outcome
        """
        # Valid entity types from API definition
        valid_entities = {
            "Email",
            "Address",
            "Person",
            "PhoneNumber",
            "PersonType",
            "Organization",
            "URL",
            "IPAddress",
            "DateTime",
            "BankAccountNumber",
            "DriversLicenseNumber",
            "PassportNumber",
        }

        # Use default values from API definition if not provided
        default_entities = ["Email", "Address"]
        entities_to_use = entities or default_entities

        # Validate entity types
        if entities:
            invalid_entities = set(entities) - valid_entities
            if invalid_entities:
                raise ValueError(
                    f"Invalid entities: {invalid_entities}. "
                    f"Valid options: {sorted(valid_entities)}"
                )

        default_thresholds = {"Email": 0.9, "Address": 0.7}
        thresholds_to_use = entity_thresholds or default_thresholds

        parameters: List[Dict[str, Any]] = [
            {"$parameterType": "enum-list", "id": "entities", "value": entities_to_use},
            {
                "$parameterType": "map-enum",
                "id": "entityThresholds",
                "value": thresholds_to_use,
            },
        ]

        return self._call_validator(
            "pii_detection",
            input_text,
            parameters,
            folder_key=folder_key,
            folder_path=folder_path,
        )

    @traced(name="guardrails_prompt_injection", run_type="uipath")
    def prompt_injection(
        self,
        input_text: str,
        *,
        threshold: Optional[float] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> GuardrailResult:
        """Detect prompt injection attempts in input text.

        Args:
            input_text: The text to validate
            threshold: Detection threshold (0.0 to 1.0, default 0.5)
            folder_key: Optional folder key for context
            folder_path: Optional folder path for context

        Returns:
            GuardrailResult indicating validation outcome
        """
        # Validate threshold range
        if threshold is not None and not (0.0 <= threshold <= 1.0):
            raise ValueError(f"Threshold must be between 0.0 and 1.0, got {threshold}")

        parameters = []
        if threshold is not None:
            parameters.append(
                {"$parameterType": "number", "id": "threshold", "value": threshold}
            )

        return self._call_validator(
            "prompt_injection",
            input_text,
            parameters,
            folder_key=folder_key,
            folder_path=folder_path,
        )

    def validate_with_policy(
        self,
        input_text: str,
        validator_name: str = "pii_detection",
        *,
        entities: Optional[List[str]] = None,
        entity_thresholds: Optional[Dict[str, float]] = None,
        threshold: Optional[float] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate text and return detailed response including reason.

        Args:
            input_text: The text to validate
            validator_name: Name of validator (pii_detection/prompt_injection)
            entities: List of PII entity types for pii_detection
            entity_thresholds: Thresholds for pii_detection
            threshold: Threshold for prompt_injection
            folder_key: Optional folder key for context
            folder_path: Optional folder path for context

        Returns:
            Dict with validation_passed, reason, and other details
        """
        parameters: List[Dict[str, Any]]

        if validator_name == "pii_detection":
            # Format parameters for PII detection
            default_entities = entities or ["Email", "Address"]
            default_thresholds = entity_thresholds or {"Email": 0.7, "Address": 0.7}

            parameters = [
                {
                    "$parameterType": "enum-list",
                    "id": "entities",
                    "value": default_entities,
                },
                {
                    "$parameterType": "map-enum",
                    "id": "entityThresholds",
                    "value": default_thresholds,
                },
            ]

        elif validator_name == "prompt_injection":
            # Format parameters for prompt injection
            parameters = []
            if threshold is not None:
                parameters.append(
                    {"$parameterType": "number", "id": "threshold", "value": threshold}
                )
        else:
            raise ValueError(f"Unsupported validator: {validator_name}")

        # Execute validation and return full response
        spec = self._validate_spec(
            validator_name=validator_name,
            input_text=input_text,
            parameters=parameters,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        )

        response_data = response.json()

        # Return the full API response with additional metadata
        return {
            "validation_passed": response_data.get("validation_passed", False),
            "reason": response_data.get("reason", ""),
            "input_text": input_text,
            "validator": validator_name,
            "parameters_used": parameters,
        }

    @traced(name="guardrails_validate_with_policy", run_type="uipath")
    def validate_with_policy_object(
        self,
        input_text: str,
        policy: GuardrailPolicy,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Validate text against a complete GuardrailPolicy object.

        Args:
            input_text: The text to validate
            policy: GuardrailPolicy object containing rules and configuration
            folder_key: Optional folder key for context
            folder_path: Optional folder path for context

        Returns:
            Dict with validation result and details
        """
        if not policy.rules:
            return {"validation_passed": True, "message": "No rules to validate"}

        # Process each rule in the policy
        for rule in policy.rules:
            if rule.validator == "pii_detection":
                entities = None
                entity_thresholds = None

                for param in rule.parameters:
                    if param.id == "entities":
                        entities = param.value
                    elif param.id == "entityThresholds":
                        entity_thresholds = param.value

                payload = {
                    "validator": rule.validator,
                    "input": input_text,
                    "parameters": [
                        {
                            "$parameterType": "enum-list",
                            "id": "entities",
                            "value": entities,
                        },
                        {
                            "$parameterType": "map-enum",
                            "id": "entityThresholds",
                            "value": entity_thresholds,
                        },
                    ],
                }

                spec = RequestSpec(
                    method="POST",
                    endpoint=Endpoint(
                        "/agentsruntime_/api/execution/guardrails/validate"
                    ),
                    json=payload,
                    headers={
                        **header_folder(folder_key, folder_path),
                    },
                )

                response = self.request(
                    spec.method,
                    url=spec.endpoint,
                    json=spec.json,
                    headers=spec.headers,
                )

                result = response.json()

                if not result.get("validation_passed", True):
                    return result

        return {"validation_passed": True, "message": "All rules passed"}

    def execute_guardrail_action(
        self,
        validation_result: Dict[str, Any],
        policy: GuardrailPolicy,
    ) -> None:
        """Execute guardrail action based on validation result and policy.

        Args:
            validation_result: Result from guardrail validation
            policy: GuardrailPolicy containing action configuration

        Raises:
            GuardrailViolationError: When PII is detected and action requires blocking
        """
        if validation_result.get("validation_passed", True):
            return

        action_type = policy.action.actionType.lower()

        # Get validator type from validation result or policy rules
        validator_name = validation_result.get("validator", "unknown")
        if validator_name == "unknown" and policy.rules:
            validator_name = policy.rules[0].validator

        if action_type == "escalate":
            print("ESCALATE DEBUG: Starting escalation process...")

            # Create generic escalation data based on policy and validation result
            data = {
                "GuardrailName": policy.name,
                "GuardrailDescription": policy.description,
                "AgentTrace": f"Agent detected {validator_name} violation in tool input",
                "ExecutionStage": "Tool Input Validation",
                "ValidatorType": validator_name,
                "Tool": policy.selector.matchNames[0]
                if policy.selector.matchNames
                else "unknown",
                "ToolInputs": validation_result.get("input_text", ""),
                "ToolOutputs": f"Blocked due to {validator_name} detection",
                "DetectedIssue": validation_result.get(
                    "reason", f"{validator_name} detected"
                ),
                "ValidationResult": validation_result,
                "PolicyName": policy.name,
                "ActionType": policy.action.actionType,
            }

            try:
                from langgraph.types import interrupt  # type: ignore[import-not-found]

                from uipath.models import CreateAction

                print(
                    f"DEBUG GUARDRAIL: Creating action with return_all_action: {policy.action.app.return_all_action}"
                )
                action_data = interrupt(
                    CreateAction(
                        app_name=policy.action.app.name,
                        title=f"{validator_name.upper().replace('_', ' ')} DETECTION - ACTION REQUIRED",
                        data=data,
                        app_version=int(policy.action.app.version),
                        app_folder_path=policy.action.app.folderName,
                        return_all_action=policy.action.app.return_all_action,
                    )
                )
                print(f"DEBUG GUARDRAIL: Action created: {action_data}")
                print(f"DEBUG GUARDRAIL: Action type: {type(action_data)}")
                if hasattr(action_data, "action"):
                    if action_data.action == "Reject":
                        print("hello\n")
                        raise GuardrailViolationError(
                            f"Request blocked by user: {validation_result.get('reason')}"
                        )
                elif (
                    hasattr(action_data, "data")
                    and action_data.data.get("Approved") is False
                ):
                    raise GuardrailViolationError(
                        f"Request blocked by user: {validation_result.get('reason')}"
                    )

            except ImportError as exc:
                print("Warning: langgraph not available for escalation actions")
                raise GuardrailViolationError(
                    f"{validator_name} detected but escalation unavailable: {validation_result.get('reason')}"
                ) from exc

        elif action_type == "block":
            reason = validation_result.get(
                "reason", f"{validator_name} or sensitive content detected"
            )
            raise GuardrailViolationError(reason)

        elif action_type == "log":
            reason = validation_result.get(
                "reason", f"{validator_name} or sensitive content detected"
            )
            print(f"GUARDRAIL LOG [{validator_name.upper()}]: {reason}")
            print(f"GUARDRAIL LOG [{validator_name.upper()}]: {reason}")
            print(f"GUARDRAIL LOG [{validator_name.upper()}]: {reason}")
            print(f"GUARDRAIL LOG [{validator_name.upper()}]: {reason}")
            print(f"GUARDRAIL LOG [{validator_name.upper()}]: {reason}")
            print(f"GUARDRAIL LOG [{validator_name.upper()}]: {reason}")
            print(f"GUARDRAIL LOG [{validator_name.upper()}]: {reason}")
