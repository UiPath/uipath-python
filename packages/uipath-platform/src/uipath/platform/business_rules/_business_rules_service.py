"""Business Rules service for UiPath Platform.

Evaluates DMN decision models deployed to Orchestrator as business rules.
"""

from typing import Any, Dict, List, Optional, Tuple

from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import FolderContext
from ..common._models import Endpoint, RequestSpec
from ..constants import HEADER_FOLDER_KEY
from ..orchestrator._folder_service import FolderService
from .business_rules import (
    BusinessRuleDecision,
    BusinessRuleError,
    BusinessRuleEvaluationResult,
    BusinessRuleStatus,
    _WireResponse,
    _WireResult,
)

_EVALUATE_ENDPOINT = Endpoint("businessrules_/v1/business-rules/evaluate")

# The service's contract is a batch; this SDK submits exactly one input under this id.
_SINGLE_INPUT_ID = "input-1"
_MAX_INPUT_KEYS = 256
_MAX_RULE_NAME_LENGTH = 256


class BusinessRulesService(FolderContext, BaseService):
    """Service for evaluating UiPath Business Rules (DMN decision models).

    Each call evaluates one input and returns the decisions it produced. The rule
    is resolved from Orchestrator by name within a folder.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: FolderService,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service

    @traced(name="business_rules_evaluate", run_type="uipath")
    def evaluate(
        self,
        rule_name: str,
        input: Dict[str, Any],
        *,
        version: Optional[str] = None,
        decision_names: Optional[List[str]] = None,
        explain: bool = False,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> BusinessRuleEvaluationResult:
        """Evaluate a deployed business rule against one input.

        Args:
            rule_name: The name of the business rule deployed to Orchestrator.
            input: The input to evaluate, keyed by DMN input name. Declared inputs
                absent from it bind to null.
            version: The rule version to evaluate; defaults to the active version.
            decision_names: The decisions to evaluate; defaults to the whole model.
            explain: Whether to record condition-level explanations in the trace.
            folder_key: The key of the folder the rule is deployed to.
            folder_path: The path of the folder the rule is deployed to. Resolved to
                a key, since the service accepts folder keys only.

        Returns:
            BusinessRuleEvaluationResult: The decisions produced for the input.

        Raises:
            ValueError: If the request is invalid or no folder can be determined.
            EnrichedException: If the service rejects the request.

        Examples:
            ```python
            from uipath.platform import UiPath

            client = UiPath()

            result = client.business_rules.evaluate(
                "Loan Pricing",
                {"creditScore": 740, "age": 34},
                folder_path="Finance",
            )
            for decision in result.decisions:
                print(decision.decision_name, decision.outputs)
            ```
        """
        _validate_rule_name(rule_name)
        _validate_input(input)
        resolved_key = self._resolve_folder_key(folder_key, folder_path)
        spec = self._evaluate_spec(
            rule_name, input, version, decision_names, explain, resolved_key
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
            scoped="tenant",
        )
        return _to_evaluation_result(_WireResponse.model_validate(response.json()))

    @traced(name="business_rules_evaluate", run_type="uipath")
    async def evaluate_async(
        self,
        rule_name: str,
        input: Dict[str, Any],
        *,
        version: Optional[str] = None,
        decision_names: Optional[List[str]] = None,
        explain: bool = False,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> BusinessRuleEvaluationResult:
        """Asynchronously evaluate a deployed business rule against one input.

        Args:
            rule_name: The name of the business rule deployed to Orchestrator.
            input: The input to evaluate, keyed by DMN input name. Declared inputs
                absent from it bind to null.
            version: The rule version to evaluate; defaults to the active version.
            decision_names: The decisions to evaluate; defaults to the whole model.
            explain: Whether to record condition-level explanations in the trace.
            folder_key: The key of the folder the rule is deployed to.
            folder_path: The path of the folder the rule is deployed to. Resolved to
                a key, since the service accepts folder keys only.

        Returns:
            BusinessRuleEvaluationResult: The decisions produced for the input.

        Raises:
            ValueError: If the request is invalid or no folder can be determined.
            EnrichedException: If the service rejects the request.
        """
        _validate_rule_name(rule_name)
        _validate_input(input)
        resolved_key = await self._resolve_folder_key_async(folder_key, folder_path)
        spec = self._evaluate_spec(
            rule_name, input, version, decision_names, explain, resolved_key
        )
        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
            scoped="tenant",
        )
        return _to_evaluation_result(_WireResponse.model_validate(response.json()))

    def _resolve_folder_key(
        self, folder_key: Optional[str], folder_path: Optional[str]
    ) -> str:
        if folder_key and folder_path:
            raise ValueError("Only one of folder_key or folder_path can be provided")
        if folder_key:
            return folder_key
        path = folder_path or (None if self._folder_key else self._folder_path)
        if path:
            return self._folders_service.retrieve_folder_key(path)  # type: ignore[return-value]
        if self._folder_key:
            return self._folder_key
        raise _missing_folder()

    async def _resolve_folder_key_async(
        self, folder_key: Optional[str], folder_path: Optional[str]
    ) -> str:
        if folder_key and folder_path:
            raise ValueError("Only one of folder_key or folder_path can be provided")
        if folder_key:
            return folder_key
        path = folder_path or (None if self._folder_key else self._folder_path)
        if path:
            return await self._folders_service.retrieve_folder_key_async(path)  # type: ignore[return-value]
        if self._folder_key:
            return self._folder_key
        raise _missing_folder()

    def _evaluate_spec(
        self,
        rule_name: str,
        input: Dict[str, Any],
        version: Optional[str],
        decision_names: Optional[List[str]],
        explain: bool,
        folder_key: str,
    ) -> RequestSpec:
        body: Dict[str, Any] = {
            "businessRuleName": rule_name,
            "explain": explain,
            "inputs": [{"id": _SINGLE_INPUT_ID, "data": input}],
        }
        if version:
            body["version"] = version
        if decision_names:
            body["decisionNames"] = decision_names
        return RequestSpec(
            method="POST",
            endpoint=_EVALUATE_ENDPOINT,
            json=body,
            headers={HEADER_FOLDER_KEY: folder_key},
        )


def _missing_folder() -> ValueError:
    return ValueError(
        "A folder is required to evaluate a deployed business rule: pass folder_key "
        "or folder_path, or set UIPATH_FOLDER_KEY or UIPATH_FOLDER_PATH"
    )


def _validate_rule_name(rule_name: str) -> None:
    if not rule_name or not rule_name.strip():
        raise ValueError("rule_name must be specified")
    if len(rule_name) > _MAX_RULE_NAME_LENGTH:
        raise ValueError(
            f"rule_name must not exceed {_MAX_RULE_NAME_LENGTH} characters"
        )
    for forbidden in ("/", "\\", "..", "%"):
        if forbidden in rule_name:
            raise ValueError(f"rule_name must not contain '{forbidden}'")
    if any(not ch.isprintable() for ch in rule_name):
        raise ValueError("rule_name must not contain control characters")


def _validate_input(input: Dict[str, Any]) -> None:
    if input is None:
        raise ValueError("input must not be None")
    if len(input) > _MAX_INPUT_KEYS:
        raise ValueError(f"input must not exceed {_MAX_INPUT_KEYS} keys")


def _single_result(
    response: _WireResponse,
) -> Tuple[List[BusinessRuleDecision], List[BusinessRuleError], BusinessRuleStatus]:
    results = response.results or []
    ours: Optional[_WireResult] = next(
        (r for r in results if r.id == _SINGLE_INPUT_ID), None
    )
    if ours is None and len(results) == 1:
        ours = results[0]
    elif ours is None and results:
        raise ValueError(
            f"The service returned {len(results)} results and none carried the id "
            f"'{_SINGLE_INPUT_ID}' this request was submitted under"
        )
    if ours is None:
        # No result for our input at all: it was never evaluated.
        return [], [], BusinessRuleStatus.ALL_FAILED

    decisions = ours.decisions or []
    errors = ours.errors or []
    if errors:
        status = BusinessRuleStatus.ALL_FAILED
    else:
        failed = sum(1 for d in decisions if d.error is not None)
        if failed == 0:
            status = BusinessRuleStatus.SUCCESS
        elif failed == len(decisions):
            status = BusinessRuleStatus.ALL_FAILED
        else:
            status = BusinessRuleStatus.PARTIAL_SUCCESS
    return decisions, errors, status


def _to_evaluation_result(response: _WireResponse) -> BusinessRuleEvaluationResult:
    decisions, errors, status = _single_result(response)
    return BusinessRuleEvaluationResult(
        status=status,
        decisions=decisions,
        errors=errors,
        top_level_error=response.error.code if response.error else None,
        business_rule_name=response.business_rule_name,
        version=response.version,
    )
