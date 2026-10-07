"""Business Rules service for UiPath Platform.

Runs business rules deployed to Orchestrator.
"""

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..common._base_service import _TRACE_PARENT_HEADER, BaseService
from ..common._bindings import resource_override
from ..common._config import UiPathApiConfig, UiPathConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import FolderContext
from ..common._models import Endpoint, RequestSpec
from ..constants import HEADER_FOLDER_KEY
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

_MAX_INPUT_KEYS = 256
_MAX_RULE_NAME_LENGTH = 256
_FORBIDDEN_RULE_NAME_PARTS = ("/", "\\", "..", "%")


@dataclass(frozen=True)
class _RunTarget:
    """Where a run goes, settled before anything is sent.

    Exactly one of ``folder_key`` and ``folder_path`` is set: a key ready to
    send, or a path still to look up.
    """

    name: str
    folder_key: Optional[str]
    folder_path: Optional[str]


class BusinessRulesService(FolderContext, BaseService):
    """Service for running UiPath Business Rules.

    Each call runs one input against a business rule deployed to Orchestrator,
    named like any other resource, and returns the decisions it produced.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: FolderService,
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service

    # Not @traced: the service records the run's decision spans under the
    # caller's span, so a client span would only duplicate them and record the
    # rule's input and outputs, which the .NET client never does either.
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
            decision_names: The decisions to evaluate; defaults to the whole model.
            folder_key: The key of the folder the rule is deployed in.
            folder_path: The path of the folder the rule is deployed in. Looked up
                and sent as its key.
            caller: Who is running the rule, for the deployed run's audit.
                Fields left unset default to the current job's values.
            trace_context: The trace to file the run's spans under. Defaults to
                the ambient trace: ``UIPATH_TRACE_ID`` and the current span.

        The rule runs in a folder named by its key: ``folder_key`` is sent as is,
        and ``folder_path`` is looked up and sent as its key; the two are
        exclusive. When the caller gives neither, it falls back to
        ``UIPATH_FOLDER_KEY`` and then ``UIPATH_FOLDER_PATH``. A ``businessRule``
        binding can remap ``name`` and the folder per environment; its folder then
        replaces ``folder_key`` or ``folder_path``.

        Returns:
            BusinessRuleRunResult: The decisions produced for the input.

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
            ```
        """
        target = self._prepare_run(name, input, folder_key, folder_path)
        spec = self._evaluate_spec(
            target.name,
            input,
            folder_key=self._resolve_folder_key(target),
            version=version,
            decision_names=decision_names,
            caller=caller,
        )
        # Called here, not in a helper: BaseService names the user agent after
        # the method that calls request(), which must be the public run().
        response = self.request(spec.method, **_request_options(spec, trace_context))
        return _to_run_result(response.json())

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
            decision_names: The decisions to evaluate; defaults to the whole model.
            folder_key: The key of the folder the rule is deployed in.
            folder_path: The path of the folder the rule is deployed in. Looked up
                and sent as its key.
            caller: Who is running the rule, for the deployed run's audit.
                Fields left unset default to the current job's values.
            trace_context: The trace to file the run's spans under. Defaults to
                the ambient trace: ``UIPATH_TRACE_ID`` and the current span.

        Returns:
            BusinessRuleRunResult: The decisions produced for the input.

        Raises:
            ValueError: If the request is invalid or a required folder is missing.
            EnrichedException: If the service rejects the request.
        """
        target = self._prepare_run(name, input, folder_key, folder_path)
        spec = self._evaluate_spec(
            target.name,
            input,
            folder_key=await self._resolve_folder_key_async(target),
            version=version,
            decision_names=decision_names,
            caller=caller,
        )
        response = await self.request_async(
            spec.method, **_request_options(spec, trace_context)
        )
        return _to_run_result(response.json())

    def _prepare_run(
        self,
        name: str,
        input: Dict[str, Any],
        folder_key: Optional[str],
        folder_path: Optional[str],
    ) -> _RunTarget:
        """Do what run() and run_async() share before the first network call.

        Applies a binding, validates the arguments and picks the folder, so only
        the folder lookup and the request itself differ between the two.
        """
        name, folder_key, folder_path = self._apply_binding(
            name, folder_key, folder_path
        )
        _validate_run_arguments(name, input)
        selected_key, selected_path = self._select_folder(folder_key, folder_path)
        return _RunTarget(name=name, folder_key=selected_key, folder_path=selected_path)

    @resource_override(resource_type="businessRule")
    def _overridden_resource(
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
        bound_name, bound_folder_path = self._overridden_resource(
            name, folder_path=folder_path
        )
        is_remapped = (bound_name, bound_folder_path) != (name, folder_path)
        if is_remapped and bound_folder_path:
            folder_key = None
        return bound_name, folder_key, bound_folder_path

    def _select_folder(
        self, folder_key: Optional[str], folder_path: Optional[str]
    ) -> Tuple[Optional[str], Optional[str]]:
        """Pick where the folder key comes from, as a ``(key, path)`` pair.

        Exactly one of the two is set: a key ready to send, or a path still to
        look up. Blank values count as not given, so they fall back to the
        environment.
        """
        has_folder_key = _has_value(folder_key)
        has_folder_path = _has_value(folder_path)
        if has_folder_key and has_folder_path:
            raise ValueError("Only one of folder_key or folder_path can be provided")
        if has_folder_key:
            return folder_key, None
        if has_folder_path:
            return None, folder_path
        if self._folder_key:
            return self._folder_key, None
        if self._folder_path:
            return None, self._folder_path
        raise ValueError(
            "A folder is required for a deployed business rule: pass folder_key or "
            "folder_path, or set UIPATH_FOLDER_KEY or UIPATH_FOLDER_PATH"
        )

    def _resolve_folder_key(self, target: _RunTarget) -> str:
        """Return the key of the folder the rule runs in, looking up a path."""
        folder_key = target.folder_key
        if target.folder_path:
            folder_key = self._folders_service.retrieve_folder_key(target.folder_path)
        return _require_folder_key(folder_key, target.folder_path)

    async def _resolve_folder_key_async(self, target: _RunTarget) -> str:
        """Asynchronously return the key of the folder the rule runs in."""
        folder_key = target.folder_key
        if target.folder_path:
            folder_key = await self._folders_service.retrieve_folder_key_async(
                target.folder_path
            )
        return _require_folder_key(folder_key, target.folder_path)

    def _evaluate_spec(
        self,
        name: str,
        input: Dict[str, Any],
        *,
        folder_key: str,
        version: Optional[str] = None,
        decision_names: Optional[List[str]] = None,
        caller: Optional[BusinessRuleCaller] = None,
    ) -> RequestSpec:
        # The service resolves the rule in this folder and files the run's trace
        # and audit record under it.
        body: Dict[str, Any] = {"businessRuleName": name, "input": input}
        if _has_value(version):
            body["version"] = version
        if decision_names:
            body["decisionNames"] = decision_names
        caller_payload = _caller_payload(caller)
        if caller_payload:
            body["caller"] = caller_payload
        return RequestSpec(
            method="POST",
            endpoint=_EVALUATE_ENDPOINT,
            json=body,
            headers={HEADER_FOLDER_KEY: folder_key},
        )


def _request_options(
    spec: RequestSpec, trace_context: Optional[TraceContext]
) -> Dict[str, Any]:
    """Return the request() arguments for a spec, besides its method."""
    return {
        "url": spec.endpoint,
        "json": spec.json,
        "headers": _headers_with_trace(spec.headers, trace_context),
        "scoped": "tenant",
    }


def _require_folder_key(folder_key: Optional[str], folder_path: Optional[str]) -> str:
    # A folder path that matches no folder looks up to None.
    if folder_key and folder_key.strip():
        return folder_key
    raise ValueError(f"No folder was found for folder_path '{folder_path}'")


def _caller_payload(caller: Optional[BusinessRuleCaller]) -> Dict[str, str]:
    """Return the caller as the service names its fields, defaulting from the job.

    Blank fields are left out, and a caller with every field blank is returned
    empty, so the request carries no caller at all.
    """
    explicit = caller or BusinessRuleCaller()
    fields = {
        "resourceKey": explicit.resource_key or UiPathConfig.process_uuid,
        "runKey": explicit.run_key or UiPathConfig.job_key,
        "folderKey": explicit.folder_key or UiPathConfig.folder_key,
    }
    payload: Dict[str, str] = {}
    for field_name, value in fields.items():
        if value and value.strip():
            payload[field_name] = value
    return payload


class _ExplicitTraceHeaders(Dict[str, str]):
    """Request headers that keep the caller's explicit trace header.

    BaseService writes the ambient trace header into the headers it is given just
    before sending; this dict ignores that write when an explicit one is set.
    """

    def __setitem__(self, key: str, value: str) -> None:
        if key == _TRACE_PARENT_HEADER and key in self:
            return
        super().__setitem__(key, value)


def _headers_with_trace(
    headers: Dict[str, str], trace_context: Optional[TraceContext]
) -> Dict[str, str]:
    """Return the headers, pinned to ``trace_context`` when the caller gave one."""
    if trace_context is None:
        return headers
    pinned_headers = _ExplicitTraceHeaders(headers)
    dict.__setitem__(
        pinned_headers, _TRACE_PARENT_HEADER, trace_context.to_traceparent()
    )
    return pinned_headers


def _has_value(value: Optional[str]) -> bool:
    # Blank counts as absent, matching how the service reads these fields.
    return bool(value and value.strip())


def _validate_run_arguments(name: str, input: Dict[str, Any]) -> None:
    _validate_rule_name(name)
    _validate_input(input)


def _validate_rule_name(name: str) -> None:
    if not _has_value(name):
        raise ValueError("name must be specified")
    if len(name) > _MAX_RULE_NAME_LENGTH:
        raise ValueError(f"name must not exceed {_MAX_RULE_NAME_LENGTH} characters")
    for forbidden_part in _FORBIDDEN_RULE_NAME_PARTS:
        if forbidden_part in name:
            raise ValueError(f"name must not contain '{forbidden_part}'")
    # Control characters only (Unicode category Cc), as the .NET client checks;
    # a non-breaking or zero-width space is allowed in a name.
    if any(unicodedata.category(character) == "Cc" for character in name):
        raise ValueError("name must not contain control characters")


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


def _overall_status(
    decisions: List[BusinessRuleDecision], errors: List[BusinessRuleError]
) -> BusinessRuleStatus:
    # An input-level error means the input never evaluated, whatever else came back.
    if errors:
        return BusinessRuleStatus.ALL_FAILED
    failed_count = sum(1 for decision in decisions if decision.error is not None)
    if failed_count == 0:
        return BusinessRuleStatus.SUCCESS
    if failed_count == len(decisions):
        return BusinessRuleStatus.ALL_FAILED
    return BusinessRuleStatus.PARTIAL_SUCCESS


def _to_run_result(response_body: Any) -> BusinessRuleRunResult:
    response = _WireResponse.model_validate(response_body)
    # A successful response always carries the input's result; one without it is
    # not an answer to report as an evaluation.
    if response.result is None:
        raise ValueError("The business rules response did not include a result")
    decisions = response.result.decisions or []
    errors = response.result.errors or []
    return BusinessRuleRunResult(
        status=_overall_status(decisions, errors),
        decisions=decisions,
        errors=errors,
        top_level_error=response.error.code if response.error else None,
        business_rule_name=response.business_rule_name,
        version=response.version,
    )
