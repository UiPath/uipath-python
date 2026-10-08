"""Business Rules service for UiPath Platform.

Runs business rules deployed to Orchestrator.
"""

import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..common._base_service import BaseService
from ..common._bindings import resource_override
from ..common._config import UiPathApiConfig, UiPathConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import FolderContext
from ..common._models import Endpoint, RequestSpec
from ..constants import HEADER_FOLDER_KEY, HEADER_TRACEPARENT_ID
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
_MAX_BUSINESS_RULE_NAME_LENGTH = 256
# The service's own rule (BusinessRuleNames in the business-rules service): a
# name may hold letters, numbers and these marks, and never "..".
_ALLOWED_BUSINESS_RULE_NAME_MARKS = frozenset(" '._()[]{}+,&@!~=:;-")


@dataclass(frozen=True)
class _RunTarget:
    """Where a run goes, settled before anything is sent.

    Exactly one of ``folder_key`` and ``folder_path`` is set: a key ready to
    send, or a path still to look up.
    """

    business_rule_name: str
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
        input_arguments: Dict[str, Any],
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
            input_arguments: The input to run, keyed by the rule's input names. Declared
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
            FolderNotFoundException: If no folder matches ``folder_path``.
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
        run_target = self._prepare_run(name, input_arguments, folder_key, folder_path)
        request_spec = self._evaluate_spec(
            run_target.business_rule_name,
            input_arguments,
            folder_key=self._resolve_folder_key(run_target),
            version=version,
            decision_names=decision_names,
            caller=caller,
        )
        # Called here, not in a helper: BaseService names the user agent after
        # the method that calls request(), which must be the public run().
        response = self.request(
            request_spec.method, **_request_options(request_spec, trace_context)
        )
        return _to_run_result(response.json())

    async def run_async(
        self,
        name: str,
        input_arguments: Dict[str, Any],
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
            input_arguments: The input to run, keyed by the rule's input names. Declared
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
            FolderNotFoundException: If no folder matches ``folder_path``.
            EnrichedException: If the service rejects the request.
        """
        run_target = self._prepare_run(name, input_arguments, folder_key, folder_path)
        request_spec = self._evaluate_spec(
            run_target.business_rule_name,
            input_arguments,
            folder_key=await self._resolve_folder_key_async(run_target),
            version=version,
            decision_names=decision_names,
            caller=caller,
        )
        response = await self.request_async(
            request_spec.method, **_request_options(request_spec, trace_context)
        )
        return _to_run_result(response.json())

    def _prepare_run(
        self,
        business_rule_name: str,
        input_arguments: Dict[str, Any],
        folder_key: Optional[str],
        folder_path: Optional[str],
    ) -> _RunTarget:
        """Do what run() and run_async() share before the first network call.

        Applies a binding, validates the arguments and picks the folder, so only
        the folder lookup and the request itself differ between the two.
        """
        business_rule_name, folder_key, folder_path = self._apply_binding(
            business_rule_name, folder_key, folder_path
        )
        _validate_run_arguments(business_rule_name, input_arguments)
        selected_key, selected_path = self._select_folder(folder_key, folder_path)
        return _RunTarget(
            business_rule_name=business_rule_name,
            folder_key=selected_key,
            folder_path=selected_path,
        )

    @resource_override(resource_type="businessRule")
    def _overridden_resource(
        self, name: str, folder_path: Optional[str] = None
    ) -> Tuple[str, Optional[str]]:
        # resource_override swaps these two arguments when the solution's
        # bindings remap this rule; the method just returns what it was given.
        return name, folder_path

    def _apply_binding(
        self,
        business_rule_name: str,
        folder_key: Optional[str],
        folder_path: Optional[str],
    ) -> Tuple[str, Optional[str], Optional[str]]:
        """Apply a businessRule binding, if one remaps this rule.

        The binding names a folder by path. When it applies, that folder
        replaces whichever folder the caller gave, including a folder_key, which
        the override decorator alone would leave in place next to the new path.
        """
        bound_business_rule_name, bound_folder_path = self._overridden_resource(
            business_rule_name, folder_path=folder_path
        )
        is_remapped = (bound_business_rule_name, bound_folder_path) != (
            business_rule_name,
            folder_path,
        )
        if is_remapped and bound_folder_path:
            folder_key = None
        return bound_business_rule_name, folder_key, bound_folder_path

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

    def _resolve_folder_key(self, run_target: _RunTarget) -> str:
        """Return the key of the folder the rule runs in, looking up a path.

        A path that matches no folder raises FolderNotFoundException.
        """
        if run_target.folder_key:
            return run_target.folder_key
        return self._folders_service.retrieve_folder_key(run_target.folder_path)

    async def _resolve_folder_key_async(self, run_target: _RunTarget) -> str:
        """Asynchronously return the key of the folder the rule runs in."""
        if run_target.folder_key:
            return run_target.folder_key
        return await self._folders_service.retrieve_folder_key_async(
            run_target.folder_path
        )

    def _evaluate_spec(
        self,
        business_rule_name: str,
        input_arguments: Dict[str, Any],
        *,
        folder_key: str,
        version: Optional[str] = None,
        decision_names: Optional[List[str]] = None,
        caller: Optional[BusinessRuleCaller] = None,
    ) -> RequestSpec:
        # The service resolves the rule in this folder and files the run's trace
        # and audit record under it.
        request_body: Dict[str, Any] = {
            "businessRuleName": business_rule_name,
            "input": input_arguments,
        }
        if _has_value(version):
            request_body["version"] = version
        if decision_names:
            request_body["decisionNames"] = decision_names
        caller_payload = _caller_payload(caller)
        if caller_payload:
            request_body["caller"] = caller_payload
        return RequestSpec(
            method="POST",
            endpoint=_EVALUATE_ENDPOINT,
            json=request_body,
            headers={HEADER_FOLDER_KEY: folder_key},
        )


def _request_options(
    request_spec: RequestSpec, trace_context: Optional[TraceContext]
) -> Dict[str, Any]:
    """Return the request() arguments for a spec, besides its method."""
    return {
        "url": request_spec.endpoint,
        "json": request_spec.json,
        "headers": _headers_with_trace(request_spec.headers, trace_context),
        "scoped": "tenant",
    }


def _caller_payload(caller: Optional[BusinessRuleCaller]) -> Dict[str, Any]:
    """Return the caller as the service names its fields, defaulting from the job.

    Blank fields are left out. ``isDebugRun`` goes with every caller, false unless
    the run is a debug session; a caller with every key blank and no debug run
    names no one, so it is returned empty and the request carries no caller.
    """
    given_caller = caller or BusinessRuleCaller()
    caller_keys = {
        "resourceKey": given_caller.resource_key or UiPathConfig.process_uuid,
        "runKey": given_caller.run_key or UiPathConfig.job_key,
        "folderKey": given_caller.folder_key or UiPathConfig.folder_key,
    }
    caller_fields: Dict[str, Any] = {}
    for field_name, field_value in caller_keys.items():
        if _has_value(field_value):
            caller_fields[field_name] = field_value
    is_debug_run = given_caller.is_debug_run
    if is_debug_run is None:
        is_debug_run = _is_debug_session()
    if not caller_fields and not is_debug_run:
        return {}
    caller_fields["isDebugRun"] = is_debug_run
    return caller_fields


def _is_debug_session() -> bool:
    # Studio Web sets the project id when it debugs; a job started from a
    # solution debug, such as Maestro's, carries isDebug in its arguments.
    return UiPathConfig.is_studio_project or UiPathConfig.is_rooted_to_debug_job


def _headers_with_trace(
    headers: Dict[str, str], trace_context: Optional[TraceContext]
) -> Dict[str, str]:
    """Return the headers, pinned to ``trace_context`` when the caller gave one.

    BaseService adds the ambient trace header only when none is set, so an
    explicit one set here is what gets sent.
    """
    if trace_context is None:
        return headers
    return {**headers, HEADER_TRACEPARENT_ID: trace_context.to_traceparent()}


def _has_value(text: Optional[str]) -> bool:
    # Blank counts as absent, matching how the service reads these fields.
    return bool(text and text.strip())


def _validate_run_arguments(
    business_rule_name: str, input_arguments: Dict[str, Any]
) -> None:
    _validate_business_rule_name(business_rule_name)
    _validate_input_arguments(input_arguments)


def _validate_business_rule_name(business_rule_name: str) -> None:
    if not _has_value(business_rule_name):
        raise ValueError("name must be specified")
    if len(business_rule_name) > _MAX_BUSINESS_RULE_NAME_LENGTH:
        raise ValueError(
            f"name must not exceed {_MAX_BUSINESS_RULE_NAME_LENGTH} characters"
        )
    disallowed_characters = sorted(
        {
            character
            for character in business_rule_name
            if not _is_allowed_business_rule_name_character(character)
        }
    )
    if disallowed_characters:
        raise ValueError(
            "name may contain only letters, numbers, spaces and "
            f"{''.join(sorted(_ALLOWED_BUSINESS_RULE_NAME_MARKS - {' '}))}; "
            f"found {', '.join(repr(character) for character in disallowed_characters)}"
        )
    if ".." in business_rule_name:
        raise ValueError("name must not contain '..'")


def _is_allowed_business_rule_name_character(character: str) -> bool:
    # Letters and numbers in any script (Unicode categories L* and N*), as the
    # service's \p{L} and \p{N} match them.
    return (
        unicodedata.category(character)[0] in ("L", "N")
        or character in _ALLOWED_BUSINESS_RULE_NAME_MARKS
    )


def _validate_input_arguments(input_arguments: Dict[str, Any]) -> None:
    if input_arguments is None:
        raise ValueError("input_arguments must not be None")
    if not isinstance(input_arguments, Mapping):
        raise ValueError(
            "input_arguments must be a mapping of the rule's input names to values, "
            f"not {type(input_arguments).__name__}"
        )
    if len(input_arguments) > _MAX_INPUT_KEYS:
        raise ValueError(f"input_arguments must not exceed {_MAX_INPUT_KEYS} keys")


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
    wire_response = _WireResponse.model_validate(response_body)
    # A successful response always carries the input's result; one without it is
    # not an answer to report as an evaluation.
    if wire_response.result is None:
        raise ValueError("The business rules response did not include a result")
    decisions = wire_response.result.decisions or []
    errors = wire_response.result.errors or []
    return BusinessRuleRunResult(
        status=_overall_status(decisions, errors),
        decisions=decisions,
        errors=errors,
        top_level_error=wire_response.error.code if wire_response.error else None,
        business_rule_name=wire_response.business_rule_name,
        version=wire_response.version,
    )
