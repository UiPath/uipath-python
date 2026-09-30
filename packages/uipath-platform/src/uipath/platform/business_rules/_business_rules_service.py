"""Business Rules service for UiPath Platform.

Runs business rules: a rule deployed to Orchestrator, or an undeployed rule
read straight from a Studio project.
"""

from collections.abc import Mapping
from typing import Any, Dict, List, Optional, Tuple

from uipath.core.tracing import traced

from ..common._base_service import _TRACE_PARENT_HEADER, BaseService
from ..common._bindings import resource_override
from ..common._config import UiPathApiConfig, UiPathConfig
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
    DebugRunContext,
    RunMode,
    TraceContext,
    _WireResponse,
    _WireResult,
)

_EVALUATE_ENDPOINT = Endpoint("businessrules_/v1/business-rules/evaluate")
_DEBUG_EVALUATE_ENDPOINT = Endpoint("businessrules_/v1/business-rules/debug/evaluate")

_HEADER_ORGANIZATION_UNIT_ID = "x-uipath-organizationunitid"
_HEADER_JOB_KEY = "x-uipath-jobkey"

_HEADER_ORGANIZATION_UNIT_ID = "x-uipath-organizationunitid"

# The service's contract is a batch; this SDK submits exactly one input under this id.
_SINGLE_INPUT_ID = "input-1"
_MAX_INPUT_KEYS = 256
_MAX_RULE_NAME_LENGTH = 256


class BusinessRulesService(FolderContext, BaseService):
    """Service for running UiPath Business Rules.

    Each call runs one input against a business rule, named like any other
    resource, and returns the decisions it produced. By default the rule
    deployed to Orchestrator runs; pass ``debug`` to run an undeployed rule from
    a Studio project instead. The caller never picks a service endpoint.
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
        name: str,
        input: Dict[str, Any],
        *,
        version: Optional[str] = None,
        debug: Optional[DebugRunContext] = None,
        decision_names: Optional[List[str]] = None,
        explain: bool = False,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
        organization_unit_id: Optional[int] = None,
        trace_context: Optional[TraceContext] = None,
    ) -> BusinessRuleRunResult:
        """Run a business rule against one input.

        Args:
            name: The name of the business rule.
            input: The input to run, keyed by the rule's input names. Declared
                inputs absent from it bind to null.
            version: The rule version to run; defaults to the active version.
                Sent with debug runs too when given.
            debug: Run the undeployed rule from a Studio project instead of the
                deployed rule.
            decision_names: The decisions to evaluate; defaults to the whole model.
            explain: Whether to record condition-level explanations in the trace.
            folder_key: The key of the folder to run in.
            folder_path: The path of the folder to run in. Looked up and sent as
                its key.
            organization_unit_id: The numeric id of the folder to run in, sent as
                given. The service prefers the folder key when both are sent.
            trace_context: The trace to file the run's spans under. Defaults to
                the ambient trace: ``UIPATH_TRACE_ID`` and the current span.

        The folder can be given as ``folder_key`` (sent as is), ``folder_path``
        (looked up and sent as its key) or ``organization_unit_id`` (sent as is);
        ``folder_key`` and ``folder_path`` are exclusive. A deployed rule needs one
        of them; a debug run by project needs none; a debug run by job lineage
        needs ``organization_unit_id``. ``explain=True`` always needs a folder key.
        When the caller gives no folder at all, it falls back to
        ``UIPATH_FOLDER_KEY`` and then ``UIPATH_FOLDER_PATH``; an explicit folder is
        never replaced by the environment's. A ``businessRule`` binding can remap
        ``name`` and the folder per environment; its folder then replaces
        ``folder_key`` or ``folder_path``.

        Returns:
            BusinessRuleRunResult: The decisions produced for the input, and the
                mode that ran.

        Raises:
            ValueError: If the request is invalid or a required folder is missing.
            EnrichedException: If the service rejects the request.

        Examples:
            ```python
            from uipath.platform import UiPath

            client = UiPath()

            result = client.business_rules.run(
                "Loan Pricing",
                {"creditScore": 740, "age": 34},
                folder_path="Finance",
            )
            for decision in result.decisions:
                print(decision.decision_name, decision.outputs)

            # An undeployed rule in a Studio project
            from uipath.platform.business_rules import DebugRunContext

            result = client.business_rules.run(
                "Loan Pricing",
                {"creditScore": 740},
                debug=DebugRunContext(project_id="0a1b2c3d-...", file_name="Loan.dmn"),
            )
            ```
        """
        name, folder_key, folder_path = self._apply_binding(
            name, folder_key, folder_path
        )
        _validate_run(name, input)
        key, path = self._folder_source(
            folder_key, folder_path, use_env=organization_unit_id is None or explain
        )
        if path:
            key = self._folders_service.retrieve_folder_key(path)
        mode, spec = self._run_spec(
            name,
            input,
            version,
            debug,
            decision_names,
            explain,
            key,
            organization_unit_id,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=_with_trace(spec.headers, trace_context),
            scoped="tenant",
        )
        return _to_run_result(mode, _WireResponse.model_validate(response.json()))

    @traced(name="business_rules_run", run_type="uipath")
    async def run_async(
        self,
        name: str,
        input: Dict[str, Any],
        *,
        version: Optional[str] = None,
        debug: Optional[DebugRunContext] = None,
        decision_names: Optional[List[str]] = None,
        explain: bool = False,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
        organization_unit_id: Optional[int] = None,
        trace_context: Optional[TraceContext] = None,
    ) -> BusinessRuleRunResult:
        """Asynchronously run a business rule against one input.

        Args:
            name: The name of the business rule.
            input: The input to run, keyed by the rule's input names. Declared
                inputs absent from it bind to null.
            version: The rule version to run; defaults to the active version.
                Sent with debug runs too when given.
            debug: Run the undeployed rule from a Studio project instead of the
                deployed rule.
            decision_names: The decisions to evaluate; defaults to the whole model.
            explain: Whether to record condition-level explanations in the trace.
            folder_key: The key of the folder to run in.
            folder_path: The path of the folder to run in. Looked up and sent as
                its key.
            organization_unit_id: The numeric id of the folder to run in, sent as
                given. The service prefers the folder key when both are sent.
            trace_context: The trace to file the run's spans under. Defaults to
                the ambient trace: ``UIPATH_TRACE_ID`` and the current span.

        Returns:
            BusinessRuleRunResult: The decisions produced for the input, and the
                mode that ran.

        Raises:
            ValueError: If the request is invalid or a required folder is missing.
            EnrichedException: If the service rejects the request.
        """
        name, folder_key, folder_path = self._apply_binding(
            name, folder_key, folder_path
        )
        _validate_run(name, input)
        key, path = self._folder_source(
            folder_key, folder_path, use_env=organization_unit_id is None or explain
        )
        if path:
            key = await self._folders_service.retrieve_folder_key_async(path)
        mode, spec = self._run_spec(
            name,
            input,
            version,
            debug,
            decision_names,
            explain,
            key,
            organization_unit_id,
        )
        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=_with_trace(spec.headers, trace_context),
            scoped="tenant",
        )
        return _to_run_result(mode, _WireResponse.model_validate(response.json()))

    @resource_override(resource_type="businessRule")
    def _binding(
        self, name: str, folder_path: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        # resource_override swaps these two arguments when the solution's
        # bindings remap this rule; the method just returns what it was given.
        return name, folder_path

    def _apply_binding(
        self, name: str, folder_key: Optional[str], folder_path: Optional[str]
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """Apply a businessRule binding, if one remaps this rule.

        The binding names a folder by path. When it applies, that folder
        replaces whichever folder the caller gave, including a folder_key, which
        the override decorator alone would leave in place next to the new path.
        """
        bound_name, bound_path = self._binding(name, folder_path=folder_path)
        if (bound_name, bound_path) != (name, folder_path) and bound_path:
            folder_key = None
        return bound_name, folder_key, bound_path

    def _folder_source(
        self, folder_key: Optional[str], folder_path: Optional[str], use_env: bool
    ) -> Tuple[Optional[str], Optional[str]]:
        """Pick the folder key to send, as a (key, path-still-to-resolve) pair.

        ``use_env`` is false when the caller named the folder another way (by its
        numeric id), so the environment's folder can't silently replace it.
        """
        if folder_key and folder_path:
            raise ValueError("Only one of folder_key or folder_path can be provided")
        if folder_key:
            return folder_key, None
        if folder_path:
            return None, folder_path
        if not use_env:
            return None, None
        if self._folder_key:
            return self._folder_key, None
        return None, self._folder_path or None

    def _run_spec(
        self,
        name: str,
        input: Dict[str, Any],
        version: Optional[str],
        debug: Optional[DebugRunContext],
        decision_names: Optional[List[str]],
        explain: bool,
        folder_key: Optional[str],
        organization_unit_id: Optional[int],
    ) -> Tuple[RunMode, RequestSpec]:
        if explain and not folder_key:
            raise _missing_folder_key()
        if debug is not None:
            return RunMode.DEBUG, self._debug_spec(
                name,
                input,
                version,
                debug,
                decision_names,
                explain,
                folder_key,
                organization_unit_id,
            )
        if not folder_key and organization_unit_id is None:
            raise _missing_folder("a deployed business rule")
        return RunMode.DEPLOYED, self._evaluate_spec(
            name,
            input,
            version,
            decision_names,
            explain,
            folder_key,
            organization_unit_id,
        )

    def _evaluate_spec(
        self,
        name: str,
        input: Dict[str, Any],
        version: Optional[str],
        decision_names: Optional[List[str]],
        explain: bool,
        folder_key: Optional[str],
        organization_unit_id: Optional[int],
    ) -> RequestSpec:
        body: Dict[str, Any] = {
            "businessRuleName": name,
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
            headers=_folder_headers(folder_key, organization_unit_id),
        )

    def _debug_spec(
        self,
        name: str,
        input: Dict[str, Any],
        version: Optional[str],
        debug: DebugRunContext,
        decision_names: Optional[List[str]],
        explain: bool,
        folder_key: Optional[str],
        organization_unit_id: Optional[int],
    ) -> RequestSpec:
        # The service finds the project one of two ways, documented as
        # alternatives: by projectId, read as given, or by businessRuleName from
        # the running debug job's lineage. Each request names the project one way
        # only; optional values the caller passes are sent as given.
        if _present(debug.project_id):
            body, headers = _project_mode(debug, organization_unit_id)
        else:
            body, headers = _job_lineage_mode(name, debug, organization_unit_id)

        body["explain"] = explain
        body["inputs"] = [{"id": _SINGLE_INPUT_ID, "data": input}]
        if version:
            body["version"] = version
        if debug.file_name:
            body["fileName"] = debug.file_name
        if decision_names:
            body["decisionNames"] = decision_names
        # Folder key: the traces service files the run's spans under it.
        if folder_key:
            headers[HEADER_FOLDER_KEY] = folder_key
        return RequestSpec(
            method="POST",
            endpoint=_DEBUG_EVALUATE_ENDPOINT,
            json=body,
            headers=headers,
        )


def _project_mode(
    debug: DebugRunContext, organization_unit_id: Optional[int]
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    # Nothing beyond the project is required. A job key or folder id the caller
    # passes anyway is sent as given; UIPATH_JOB_KEY is not added on its own.
    headers: Dict[str, str] = {}
    job_key = debug.job_key
    if job_key and job_key.strip():
        headers[_HEADER_JOB_KEY] = job_key
    if organization_unit_id is not None:
        headers[_HEADER_ORGANIZATION_UNIT_ID] = str(organization_unit_id)
    return {"projectId": debug.project_id}, headers


def _job_lineage_mode(
    name: str, debug: DebugRunContext, organization_unit_id: Optional[int]
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    job_key = debug.job_key or UiPathConfig.job_key
    if not job_key or not job_key.strip():
        raise ValueError(
            "debug.job_key must be specified when debug.project_id is not: "
            "the service resolves the project from the job's lineage. "
            "Set it or UIPATH_JOB_KEY."
        )
    if organization_unit_id is None:
        raise ValueError(
            "organization_unit_id must be specified when debug.project_id is not: "
            "it is the folder the job's lineage is read under"
        )
    headers = {
        _HEADER_JOB_KEY: job_key,
        _HEADER_ORGANIZATION_UNIT_ID: str(organization_unit_id),
    }
    return {"businessRuleName": name}, headers


class _TraceHeaders(Dict[str, str]):
    """Request headers that keep the caller's explicit trace header.

    BaseService writes the ambient trace header into the headers it is given just
    before sending; this dict ignores that write when an explicit one is set.
    """

    def __setitem__(self, key: str, value: str) -> None:
        if key == _TRACE_PARENT_HEADER and key in self:
            return
        super().__setitem__(key, value)


def _with_trace(
    headers: Dict[str, str], trace_context: Optional[TraceContext]
) -> Dict[str, str]:
    if trace_context is None:
        return headers
    pinned = _TraceHeaders(headers)
    dict.__setitem__(pinned, _TRACE_PARENT_HEADER, trace_context.to_traceparent())
    return pinned


def _present(value: Optional[str]) -> bool:
    # Blank counts as absent, matching how the service reads these fields.
    return bool(value and value.strip())


def _folder_headers(
    folder_key: Optional[str], organization_unit_id: Optional[int]
) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if folder_key:
        headers[HEADER_FOLDER_KEY] = folder_key
    if organization_unit_id is not None:
        headers[_HEADER_ORGANIZATION_UNIT_ID] = str(organization_unit_id)
    return headers


def _missing_folder(needed_for: str) -> ValueError:
    return ValueError(
        f"A folder is required for {needed_for}: pass folder_key, folder_path or "
        "organization_unit_id, or set UIPATH_FOLDER_KEY or UIPATH_FOLDER_PATH"
    )


def _missing_folder_key() -> ValueError:
    return ValueError(
        "A folder key is required for explain=True: pass folder_key or "
        "folder_path, or set UIPATH_FOLDER_KEY or UIPATH_FOLDER_PATH"
    )


def _validate_run(name: str, input: Dict[str, Any]) -> None:
    _validate_rule_name(name, "name")
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
    if not isinstance(input, Mapping):
        raise ValueError(
            "input must be a mapping of the rule's input names to values, "
            f"not {type(input).__name__}"
        )
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
    deployed = mode == RunMode.DEPLOYED
    return BusinessRuleRunResult(
        mode=mode,
        status=status,
        decisions=decisions,
        errors=errors,
        top_level_error=response.error.code if response.error else None,
        business_rule_name=response.business_rule_name if deployed else None,
        version=response.version if deployed else None,
        project_id=None if deployed else response.project_id,
        file_name=None if deployed else response.file_name,
    )
