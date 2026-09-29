"""Business Rules service for UiPath Platform.

Runs DMN decision models deployed to Orchestrator as business rules.
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
    BusinessRuleRunResult,
    BusinessRuleStatus,
    DeployedRunContext,
    RunMode,
    _WireResponse,
    _WireResult,
)

_EVALUATE_ENDPOINT = Endpoint("businessrules_/v1/business-rules/evaluate")

# The service's contract is a batch; this SDK submits exactly one input under this id.
_SINGLE_INPUT_ID = "input-1"
_MAX_INPUT_KEYS = 256
_MAX_RULE_NAME_LENGTH = 256


class BusinessRulesService(FolderContext, BaseService):
    """Service for running UiPath Business Rules (DMN decision models).

    Each call runs one input and returns the decisions it produced. Which model
    runs is set by the run context; ``deployed`` names a rule deployed to
    Orchestrator. The caller never picks a service endpoint.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: FolderService,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service

    @traced(name="business_rules_run", run_type="uipath")
    def run(
        self,
        input: Dict[str, Any],
        *,
        deployed: DeployedRunContext,
        decision_names: Optional[List[str]] = None,
        explain: bool = False,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> BusinessRuleRunResult:
        """Run a business rule against one input.

        Args:
            input: The input to run, keyed by DMN input name. Declared inputs absent
                from it bind to null.
            deployed: The business rule deployed to Orchestrator to run.
            decision_names: The decisions to evaluate; defaults to the whole model.
            explain: Whether to record condition-level explanations in the trace.
            folder_key: The key of the folder to run in.
            folder_path: The path of the folder to run in. Resolved to a key, since
                the service accepts folder keys only.

        A folder is required. When neither ``folder_key`` nor ``folder_path`` is given, it falls back to
        ``UIPATH_FOLDER_KEY`` and then ``UIPATH_FOLDER_PATH``.

        Returns:
            BusinessRuleRunResult: The decisions produced for the input, and the
                mode that ran.

        Raises:
            ValueError: If the request is invalid or a required folder is missing.
            EnrichedException: If the service rejects the request.

        Examples:
            ```python
            from uipath.platform import UiPath
            from uipath.platform.business_rules import DeployedRunContext

            client = UiPath()

            result = client.business_rules.run(
                {"creditScore": 740, "age": 34},
                deployed=DeployedRunContext(rule_name="Loan Pricing"),
                folder_path="Finance",
            )
            for decision in result.decisions:
                print(decision.decision_name, decision.outputs)
            ```
        """
        _validate_run(input, deployed)
        key, path = self._folder_source(folder_key, folder_path)
        if path:
            key = self._folders_service.retrieve_folder_key(path)
        mode, spec = self._run_spec(input, deployed, decision_names, explain, key)
        response = self.request(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
            scoped="tenant",
        )
        return _to_run_result(mode, _WireResponse.model_validate(response.json()))

    @traced(name="business_rules_run", run_type="uipath")
    async def run_async(
        self,
        input: Dict[str, Any],
        *,
        deployed: DeployedRunContext,
        decision_names: Optional[List[str]] = None,
        explain: bool = False,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> BusinessRuleRunResult:
        """Asynchronously run a business rule against one input.

        Args:
            input: The input to run, keyed by DMN input name. Declared inputs absent
                from it bind to null.
            deployed: The business rule deployed to Orchestrator to run.
            decision_names: The decisions to evaluate; defaults to the whole model.
            explain: Whether to record condition-level explanations in the trace.
            folder_key: The key of the folder to run in.
            folder_path: The path of the folder to run in. Resolved to a key, since
                the service accepts folder keys only.

        Returns:
            BusinessRuleRunResult: The decisions produced for the input, and the
                mode that ran.

        Raises:
            ValueError: If the request is invalid or a required folder is missing.
            EnrichedException: If the service rejects the request.
        """
        _validate_run(input, deployed)
        key, path = self._folder_source(folder_key, folder_path)
        if path:
            key = await self._folders_service.retrieve_folder_key_async(path)
        mode, spec = self._run_spec(input, deployed, decision_names, explain, key)
        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
            scoped="tenant",
        )
        return _to_run_result(mode, _WireResponse.model_validate(response.json()))

    def _folder_source(
        self, folder_key: Optional[str], folder_path: Optional[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Pick the folder to run in, as a (key, path-still-to-resolve) pair."""
        if folder_key and folder_path:
            raise ValueError("Only one of folder_key or folder_path can be provided")
        if folder_key:
            return folder_key, None
        if folder_path:
            return None, folder_path
        if self._folder_key:
            return self._folder_key, None
        return None, self._folder_path or None

    def _run_spec(
        self,
        input: Dict[str, Any],
        deployed: DeployedRunContext,
        decision_names: Optional[List[str]],
        explain: bool,
        folder_key: Optional[str],
    ) -> Tuple[RunMode, RequestSpec]:
        if not folder_key:
            raise _missing_folder("a deployed business rule")
        return RunMode.DEPLOYED, self._evaluate_spec(
            input, deployed, decision_names, explain, folder_key
        )

    def _evaluate_spec(
        self,
        input: Dict[str, Any],
        deployed: DeployedRunContext,
        decision_names: Optional[List[str]],
        explain: bool,
        folder_key: str,
    ) -> RequestSpec:
        body: Dict[str, Any] = {
            "businessRuleName": deployed.rule_name,
            "explain": explain,
            "inputs": [{"id": _SINGLE_INPUT_ID, "data": input}],
        }
        if deployed.version:
            body["version"] = deployed.version
        if decision_names:
            body["decisionNames"] = decision_names
        return RequestSpec(
            method="POST",
            endpoint=_EVALUATE_ENDPOINT,
            json=body,
            headers={HEADER_FOLDER_KEY: folder_key},
        )


def _present(value: Optional[str]) -> bool:
    # Blank counts as absent, matching how the service reads these fields.
    return bool(value and value.strip())


def _missing_folder(needed_for: str) -> ValueError:
    return ValueError(
        f"A folder is required for {needed_for}: pass folder_key or folder_path, "
        "or set UIPATH_FOLDER_KEY or UIPATH_FOLDER_PATH"
    )


def _validate_run(input: Dict[str, Any], deployed: DeployedRunContext) -> None:
    if deployed is None:
        raise ValueError("deployed must be set")
    _validate_rule_name(deployed.rule_name, "deployed.rule_name")
    _validate_input(input)


def _validate_rule_name(rule_name: str, field: str) -> None:
    if not _present(rule_name):
        raise ValueError(f"{field} must be specified")
    if len(rule_name) > _MAX_RULE_NAME_LENGTH:
        raise ValueError(f"{field} must not exceed {_MAX_RULE_NAME_LENGTH} characters")
    for forbidden in ("/", "\\", "..", "%"):
        if forbidden in rule_name:
            raise ValueError(f"{field} must not contain '{forbidden}'")
    if any(not ch.isprintable() for ch in rule_name):
        raise ValueError(f"{field} must not contain control characters")


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


def _to_run_result(mode: RunMode, response: _WireResponse) -> BusinessRuleRunResult:
    decisions, errors, status = _single_result(response)
    return BusinessRuleRunResult(
        mode=mode,
        status=status,
        decisions=decisions,
        errors=errors,
        top_level_error=response.error.code if response.error else None,
        business_rule_name=response.business_rule_name,
        version=response.version,
    )
