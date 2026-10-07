"""Business Rules service for UiPath Platform.

Runs business rules: a rule deployed to Orchestrator, or, inside a debug
session, the undeployed rule from the Studio project being debugged.
"""

import unicodedata
from collections.abc import Mapping
from typing import Any, Dict, List, Optional, Tuple

from uipath.core.tracing import traced

from ..common._base_service import _TRACE_PARENT_HEADER, BaseService
from ..common._bindings import resource_override
from ..common._config import UiPathApiConfig, UiPathConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import FolderContext
from ..common._models import Endpoint, RequestSpec
from ..constants import HEADER_FOLDER_KEY, HEADER_JOB_KEY
from ..orchestrator._folder_service import FolderService
from .business_rules import (
    BusinessRuleCaller,
    BusinessRuleDecision,
    BusinessRuleError,
    BusinessRuleRunResult,
    BusinessRuleStatus,
    TraceContext,
    _WireResponse,
)

_EVALUATE_ENDPOINT = Endpoint("businessrules_/v1/business-rules/evaluate")
_DEBUG_EVALUATE_ENDPOINT = Endpoint("businessrules_/v1/business-rules/debug/evaluate")

_MAX_INPUT_KEYS = 256
_MAX_RULE_NAME_LENGTH = 256


class BusinessRulesService(FolderContext, BaseService):
    """Service for running UiPath Business Rules.

    Each call runs one input against a business rule, named like any other
    resource, and returns the decisions it produced. The service picks the
    endpoint from the run itself, so the caller never chooses one: inside a debug
    session the undeployed rule from the project being debugged runs, and
    otherwise the rule deployed to Orchestrator runs.
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
        decision_names: Optional[List[str]] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
        caller: Optional[BusinessRuleCaller] = None,
        trace_context: Optional[TraceContext] = None,
    ) -> BusinessRuleRunResult:
        """Run a business rule against one input.

        Args:
            name: The name of the business rule.
            input: The input to run, keyed by the rule's input names. Declared
                inputs absent from it bind to null.
            version: The rule version to run; defaults to the active version.
                Ignored on a debug run.
            decision_names: The decisions to evaluate; defaults to the whole model.
            folder_key: The key of the folder the rule is deployed in.
            folder_path: The path of the folder the rule is deployed in. Looked up
                and sent as its key.
            caller: Who is running the rule, for the deployed run's audit.
                Fields left unset default to the current job's values. Ignored
                on a debug run.
            trace_context: The trace to file the run's spans under. Defaults to
                the ambient trace: ``UIPATH_TRACE_ID`` and the current span.

        Which rule runs is decided in this order, first match winning:

        1. ``folder_key`` or ``folder_path`` given: the rule deployed in that
           folder.
        2. Inside a debug session (``UIPATH_PROJECT_ID`` is set, or the job is
           rooted to a debug job) with a job key in ``UIPATH_JOB_KEY``: the
           undeployed rule from the project being debugged. The service finds the
           project and its folders from the job's lineage.
        3. Otherwise: the rule deployed in ``UIPATH_FOLDER_KEY``, or else
           ``UIPATH_FOLDER_PATH``.

        A deployed run needs a folder key: ``folder_key`` is sent as is, and
        ``folder_path`` is looked up and sent as its key; the two are exclusive.
        A ``businessRule`` binding can remap ``name`` and the folder per
        environment; its folder then replaces ``folder_key`` or ``folder_path``.

        Returns:
            BusinessRuleRunResult: The decisions produced for the input.

        Raises:
            ValueError: If the request is invalid or a required folder is missing.
            EnrichedException: If the service rejects the request.

        Examples:
            ```python
            from uipath.platform import UiPath

            client = UiPath()

            # In a debug session this runs the rule from the project being
            # debugged; deployed, the rule in the job's folder.
            result = client.business_rules.run(
                "Loan Pricing", {"creditScore": 740, "age": 34}
            )
            for decision in result.decisions:
                print(decision.decision_name, decision.outputs)

            # Always the rule deployed in a given folder
            result = client.business_rules.run(
                "Loan Pricing", {"creditScore": 740}, folder_path="Finance"
            )
            ```
        """
        debug_job_key = _debug_job_key(folder_key, folder_path)
        name, folder_key, folder_path = self._apply_binding(
            name, folder_key, folder_path
        )
        _validate_run(name, input)
        if debug_job_key:
            spec = _debug_spec(name, input, debug_job_key, decision_names)
        else:
            key, path = self._folder_source(folder_key, folder_path)
            if path:
                key = self._folders_service.retrieve_folder_key(path)
            spec = _evaluate_spec(name, input, version, decision_names, key, caller)
        response = self.request(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=_with_trace(spec.headers, trace_context),
            scoped="tenant",
        )
        return _to_run_result(_WireResponse.model_validate(response.json()))

    @traced(name="business_rules_run", run_type="uipath")
    async def run_async(
        self,
        name: str,
        input: Dict[str, Any],
        *,
        version: Optional[str] = None,
        decision_names: Optional[List[str]] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
        caller: Optional[BusinessRuleCaller] = None,
        trace_context: Optional[TraceContext] = None,
    ) -> BusinessRuleRunResult:
        """Asynchronously run a business rule against one input.

        Args:
            name: The name of the business rule.
            input: The input to run, keyed by the rule's input names. Declared
                inputs absent from it bind to null.
            version: The rule version to run; defaults to the active version.
                Ignored on a debug run.
            decision_names: The decisions to evaluate; defaults to the whole model.
            folder_key: The key of the folder the rule is deployed in.
            folder_path: The path of the folder the rule is deployed in. Looked up
                and sent as its key.
            caller: Who is running the rule, for the deployed run's audit.
                Fields left unset default to the current job's values. Ignored
                on a debug run.
            trace_context: The trace to file the run's spans under. Defaults to
                the ambient trace: ``UIPATH_TRACE_ID`` and the current span.

        Returns:
            BusinessRuleRunResult: The decisions produced for the input.

        Raises:
            ValueError: If the request is invalid or a required folder is missing.
            EnrichedException: If the service rejects the request.
        """
        debug_job_key = _debug_job_key(folder_key, folder_path)
        name, folder_key, folder_path = self._apply_binding(
            name, folder_key, folder_path
        )
        _validate_run(name, input)
        if debug_job_key:
            spec = _debug_spec(name, input, debug_job_key, decision_names)
        else:
            key, path = self._folder_source(folder_key, folder_path)
            if path:
                key = await self._folders_service.retrieve_folder_key_async(path)
            spec = _evaluate_spec(name, input, version, decision_names, key, caller)
        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=_with_trace(spec.headers, trace_context),
            scoped="tenant",
        )
        return _to_run_result(_WireResponse.model_validate(response.json()))

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
        self, folder_key: Optional[str], folder_path: Optional[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Pick the folder key to send, as a (key, path-still-to-resolve) pair."""
        # Blank counts as not given, so it falls back to the environment.
        has_key, has_path = _present(folder_key), _present(folder_path)
        if has_key and has_path:
            raise ValueError("Only one of folder_key or folder_path can be provided")
        if has_key:
            return folder_key, None
        if has_path:
            return None, folder_path
        if self._folder_key:
            return self._folder_key, None
        if self._folder_path:
            return None, self._folder_path
        raise ValueError(
            "A folder is required for a deployed business rule: pass folder_key or "
            "folder_path, or set UIPATH_FOLDER_KEY or UIPATH_FOLDER_PATH"
        )


def _evaluate_spec(
    name: str,
    input: Dict[str, Any],
    version: Optional[str],
    decision_names: Optional[List[str]],
    folder_key: Optional[str],
    caller: Optional[BusinessRuleCaller],
) -> RequestSpec:
    # The service resolves the rule in this folder and files the run's trace and
    # audit record under it; a folder path that resolves to nothing lands here.
    if not folder_key or not folder_key.strip():
        raise ValueError(f"No folder key was found for business rule '{name}'")
    body: Dict[str, Any] = {"businessRuleName": name, "input": input}
    if _present(version):
        body["version"] = version
    if decision_names:
        body["decisionNames"] = decision_names
    wire_caller = _wire_caller(caller)
    if wire_caller:
        body["caller"] = wire_caller
    return RequestSpec(
        method="POST",
        endpoint=_EVALUATE_ENDPOINT,
        json=body,
        headers={HEADER_FOLDER_KEY: folder_key},
    )


def _debug_job_key(
    folder_key: Optional[str], folder_path: Optional[str]
) -> Optional[str]:
    """Return the debug job's key when this run is a debug run, else None.

    A folder the caller names always means a deployed rule. Otherwise a run in a
    debug session debugs the project, named by the session's job; without a job
    key there is no lineage to resolve the project from, so it runs deployed.
    """
    if _present(folder_key) or _present(folder_path):
        return None
    if not (UiPathConfig.is_studio_project or UiPathConfig.is_rooted_to_debug_job):
        return None
    job_key = UiPathConfig.job_key
    return job_key if job_key and job_key.strip() else None


def _debug_spec(
    name: str,
    input: Dict[str, Any],
    job_key: str,
    decision_names: Optional[List[str]],
) -> RequestSpec:
    # The service finds the project, and the folders the job ran in, from the
    # debug job's lineage, and checks the rule name against it. No folder header
    # is sent, and neither is a version or caller: an undeployed rule has no
    # version, and a debug run is not an audited execution.
    body: Dict[str, Any] = {"businessRuleName": name, "input": input}
    if decision_names:
        body["decisionNames"] = decision_names
    return RequestSpec(
        method="POST",
        endpoint=_DEBUG_EVALUATE_ENDPOINT,
        json=body,
        headers={HEADER_JOB_KEY: job_key},
    )


def _wire_caller(caller: Optional[BusinessRuleCaller]) -> Dict[str, str]:
    given = caller or BusinessRuleCaller()
    values = {
        "resourceKey": given.resource_key or UiPathConfig.process_uuid,
        "runKey": given.run_key or UiPathConfig.job_key,
        "folderKey": given.folder_key or UiPathConfig.folder_key,
    }
    # Blank fields are left out, and a caller with every field blank is no caller.
    wire: Dict[str, str] = {}
    for key, value in values.items():
        if value and value.strip():
            wire[key] = value
    return wire


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
    # Control characters only (Unicode category Cc), as the .NET client checks;
    # a non-breaking or zero-width space is allowed in a name.
    if any(unicodedata.category(ch) == "Cc" for ch in rule_name):
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


def _status(
    decisions: List[BusinessRuleDecision], errors: List[BusinessRuleError]
) -> BusinessRuleStatus:
    # An input-level error means the input never evaluated, whatever else came back.
    if errors:
        return BusinessRuleStatus.ALL_FAILED
    failed = sum(1 for d in decisions if d.error is not None)
    if failed == 0:
        return BusinessRuleStatus.SUCCESS
    if failed == len(decisions):
        return BusinessRuleStatus.ALL_FAILED
    return BusinessRuleStatus.PARTIAL_SUCCESS


def _to_run_result(response: _WireResponse) -> BusinessRuleRunResult:
    # A successful response always carries the input's result; one without it is
    # not an answer to report as an evaluation.
    if response.result is None:
        raise ValueError("The business rules response did not include a result")
    decisions = response.result.decisions or []
    errors = response.result.errors or []
    return BusinessRuleRunResult(
        status=_status(decisions, errors),
        decisions=decisions,
        errors=errors,
        top_level_error=response.error.code if response.error else None,
        business_rule_name=response.business_rule_name,
        version=response.version,
        project_id=response.project_id,
        file_name=response.file_name,
    )
