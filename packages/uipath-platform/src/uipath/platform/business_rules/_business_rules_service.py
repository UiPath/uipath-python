"""Business Rules service for UiPath Platform.

Runs DMN decision models: a business rule deployed to Orchestrator, or an
undeployed DMN read straight from a Studio project.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Iterator, List, Optional, Tuple

from httpx import Request
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

# The service's contract is a batch; this SDK submits exactly one input under this id.
_SINGLE_INPUT_ID = "input-1"
_MAX_INPUT_KEYS = 256
_MAX_RULE_NAME_LENGTH = 256

# The caller's explicit trace for the run in progress. BaseService always sets
# the ambient trace header, so a request hook on this service's own clients
# replaces it just before sending. A ContextVar keeps concurrent runs apart.
_explicit_traceparent: ContextVar[Optional[str]] = ContextVar(
    "business_rules_traceparent", default=None
)


class BusinessRulesService(FolderContext, BaseService):
    """Service for running UiPath Business Rules (DMN decision models).

    Each call runs one input against a business rule, named like any other
    resource, and returns the decisions it produced. By default the rule
    deployed to Orchestrator runs; pass ``debug`` to run an undeployed DMN from
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
        sync_hooks = self._client.event_hooks
        sync_hooks["request"] = [*sync_hooks.get("request", []), _apply_traceparent]
        self._client.event_hooks = sync_hooks
        async_hooks = self._client_async.event_hooks
        async_hooks["request"] = [
            *async_hooks.get("request", []),
            _apply_traceparent_async,
        ]
        self._client_async.event_hooks = async_hooks

    @resource_override(resource_type="businessRule")
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
        trace_context: Optional[TraceContext] = None,
    ) -> BusinessRuleRunResult:
        """Run a business rule against one input.

        Args:
            name: The name of the business rule.
            input: The input to run, keyed by the rule's input names. Declared
                inputs absent from it bind to null.
            version: The deployed rule version to run; defaults to the active
                version. Not used with ``debug``.
            debug: Run an undeployed DMN from a Studio project instead of the
                deployed rule.
            decision_names: The decisions to evaluate; defaults to the whole model.
            explain: Whether to record condition-level explanations in the trace.
            folder_key: The key of the folder to run in.
            folder_path: The path of the folder to run in. Resolved to a key, since
                the service accepts folder keys only.
            trace_context: The trace to file the run's spans under. Defaults to
                the ambient trace: ``UIPATH_TRACE_ID`` and the current span.

        A folder is required for a deployed rule and whenever ``explain`` is set.
        When neither ``folder_key`` nor ``folder_path`` is given, it falls back to ``UIPATH_FOLDER_KEY`` and then
        ``UIPATH_FOLDER_PATH``. ``name`` and ``folder_path`` can be overridden per
        environment through the project's ``businessRule`` bindings.

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

            # An undeployed DMN in a Studio project
            from uipath.platform.business_rules import DebugRunContext

            result = client.business_rules.run(
                "Loan Pricing",
                {"creditScore": 740},
                debug=DebugRunContext(project_id="0a1b2c3d-...", file_name="Loan.dmn"),
            )
            ```
        """
        _validate_run(name, input, version, debug)
        key, path = self._folder_source(folder_key, folder_path)
        if path:
            key = self._folders_service.retrieve_folder_key(path)
        mode, spec = self._run_spec(
            name, input, version, debug, decision_names, explain, key
        )
        with _trace_override(trace_context):
            response = self.request(
                spec.method,
                url=spec.endpoint,
                json=spec.json,
                headers=spec.headers,
                scoped="tenant",
            )
        return _to_run_result(mode, _WireResponse.model_validate(response.json()))

    @resource_override(resource_type="businessRule")
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
        trace_context: Optional[TraceContext] = None,
    ) -> BusinessRuleRunResult:
        """Asynchronously run a business rule against one input.

        Args:
            name: The name of the business rule.
            input: The input to run, keyed by the rule's input names. Declared
                inputs absent from it bind to null.
            version: The deployed rule version to run; defaults to the active
                version. Not used with ``debug``.
            debug: Run an undeployed DMN from a Studio project instead of the
                deployed rule.
            decision_names: The decisions to evaluate; defaults to the whole model.
            explain: Whether to record condition-level explanations in the trace.
            folder_key: The key of the folder to run in.
            folder_path: The path of the folder to run in. Resolved to a key, since
                the service accepts folder keys only.
            trace_context: The trace to file the run's spans under. Defaults to
                the ambient trace: ``UIPATH_TRACE_ID`` and the current span.

        Returns:
            BusinessRuleRunResult: The decisions produced for the input, and the
                mode that ran.

        Raises:
            ValueError: If the request is invalid or a required folder is missing.
            EnrichedException: If the service rejects the request.
        """
        _validate_run(name, input, version, debug)
        key, path = self._folder_source(folder_key, folder_path)
        if path:
            key = await self._folders_service.retrieve_folder_key_async(path)
        mode, spec = self._run_spec(
            name, input, version, debug, decision_names, explain, key
        )
        with _trace_override(trace_context):
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
        name: str,
        input: Dict[str, Any],
        version: Optional[str],
        debug: Optional[DebugRunContext],
        decision_names: Optional[List[str]],
        explain: bool,
        folder_key: Optional[str],
    ) -> Tuple[RunMode, RequestSpec]:
        if debug is not None:
            if explain and not folder_key:
                raise _missing_folder("explain=True")
            return RunMode.DEBUG, self._debug_spec(
                name, input, debug, decision_names, explain, folder_key
            )
        if not folder_key:
            raise _missing_folder("a deployed business rule")
        return RunMode.DEPLOYED, self._evaluate_spec(
            name, input, version, decision_names, explain, folder_key
        )

    def _evaluate_spec(
        self,
        name: str,
        input: Dict[str, Any],
        version: Optional[str],
        decision_names: Optional[List[str]],
        explain: bool,
        folder_key: str,
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
            headers={HEADER_FOLDER_KEY: folder_key},
        )

    def _debug_spec(
        self,
        name: str,
        input: Dict[str, Any],
        debug: DebugRunContext,
        decision_names: Optional[List[str]],
        explain: bool,
        folder_key: Optional[str],
    ) -> RequestSpec:
        job_key = debug.job_key or UiPathConfig.job_key
        # A named project is used as given. Without one, the service resolves
        # the project from the job's lineage, which needs the job and its folder.
        if not _present(debug.project_id):
            if not _present(job_key):
                raise ValueError(
                    "debug.job_key must be specified when debug.project_id is not: "
                    "the service resolves the project from the job's lineage. "
                    "Set it or UIPATH_JOB_KEY."
                )
            if debug.organization_unit_id is None:
                raise ValueError(
                    "debug.organization_unit_id must be specified when "
                    "debug.project_id is not: it is the folder the job's lineage "
                    "is read under"
                )

        body: Dict[str, Any] = {
            "businessRuleName": name,
            "explain": explain,
            "inputs": [{"id": _SINGLE_INPUT_ID, "data": input}],
        }
        if debug.project_id:
            body["projectId"] = debug.project_id
        if debug.file_name:
            body["fileName"] = debug.file_name
        if decision_names:
            body["decisionNames"] = decision_names

        # Folder key: the traces service files the run's spans under it.
        headers: Dict[str, str] = {}
        if folder_key:
            headers[HEADER_FOLDER_KEY] = folder_key
        if debug.organization_unit_id is not None:
            headers[_HEADER_ORGANIZATION_UNIT_ID] = str(debug.organization_unit_id)
        if job_key:
            headers[_HEADER_JOB_KEY] = job_key
        return RequestSpec(
            method="POST",
            endpoint=_DEBUG_EVALUATE_ENDPOINT,
            json=body,
            headers=headers,
        )


@contextmanager
def _trace_override(trace_context: Optional[TraceContext]) -> Iterator[None]:
    token = _explicit_traceparent.set(
        trace_context.to_traceparent() if trace_context else None
    )
    try:
        yield
    finally:
        _explicit_traceparent.reset(token)


def _apply_traceparent(request: Request) -> None:
    traceparent = _explicit_traceparent.get()
    if traceparent:
        request.headers[_TRACE_PARENT_HEADER] = traceparent


async def _apply_traceparent_async(request: Request) -> None:
    _apply_traceparent(request)


def _present(value: Optional[str]) -> bool:
    # Blank counts as absent, matching how the service reads these fields.
    return bool(value and value.strip())


def _missing_folder(needed_for: str) -> ValueError:
    return ValueError(
        f"A folder is required for {needed_for}: pass folder_key or folder_path, "
        "or set UIPATH_FOLDER_KEY or UIPATH_FOLDER_PATH"
    )


def _validate_run(
    name: str,
    input: Dict[str, Any],
    version: Optional[str],
    debug: Optional[DebugRunContext],
) -> None:
    _validate_rule_name(name, "name")
    if debug is not None and version:
        raise ValueError(
            "version applies to deployed rules only; a debug run reads the "
            "project as it is"
        )
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
