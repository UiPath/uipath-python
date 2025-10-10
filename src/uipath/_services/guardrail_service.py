from enum import Enum
from typing import Any, Dict, Optional

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder
from ..tracing import traced
from ._base_service import BaseService


class GuardrailResult(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"


class GuardrailsService(FolderContext, BaseService):
    """Service for validating text against UiPath Guardrails."""

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

    def _call_validator(
        self,
        validator_name: str,
        input_text: str,
        parameters: Dict[str, Any],
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
        result = response.json().get("result")
        return GuardrailResult(result)

    def _validate_spec(
        self,
        validator_name: str,
        input_text: str,
        parameters: Dict[str, Any],
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        payload = {
            "validator": validator_name,
            "input": input_text,
            "parameters": parameters or {},
        }

        return RequestSpec(
            method="POST",
            endpoint=Endpoint("/api/execution/guardrails/validate"),
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
            url=Endpoint("/api/execution/guardrails/definitions"),
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
        entities: Optional[list] = None,
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

        parameters = {
            "entities": entities_to_use,
            "entityThresholds": entity_thresholds or {"Email": 0.9, "Address": 0.7},
        }

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

        parameters = {}
        if threshold is not None:
            parameters["threshold"] = threshold

        return self._call_validator(
            "prompt_injection",
            input_text,
            parameters,
            folder_key=folder_key,
            folder_path=folder_path,
        )
