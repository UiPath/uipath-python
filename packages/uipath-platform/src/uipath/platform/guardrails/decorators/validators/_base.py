"""Abstract base classes for guardrail validators."""

import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar

from uipath.core.guardrails import GuardrailValidationResult

from uipath.platform.errors import EnrichedException
from uipath.platform.guardrails.attachments import (
    APPLIES_TO_PARAMETER_ID,
    DetectionScope,
    scope_includes_files,
    with_detection_scope,
)
from uipath.platform.guardrails.guardrails import (
    BuiltInValidatorGuardrail,
    GuardrailAttachment,
)

from .._enums import GuardrailExecutionStage

logger = logging.getLogger(__name__)


def _declares_detection_scope(guardrail: BuiltInValidatorGuardrail) -> bool:
    try:
        return any(
            parameter.id.lower() == APPLIES_TO_PARAMETER_ID.lower()
            and isinstance(parameter.value, str)
            and bool(parameter.value.strip())
            for parameter in guardrail.validator_parameters
        )
    except Exception:
        return False


class GuardrailValidatorBase:
    """Root base class for guardrail validators.

    Concrete validators should subclass either
    `BuiltInGuardrailValidator` (for UiPath API-backed validation)
    or `CustomGuardrailValidator` (for in-process Python validation).
    """

    supported_stages: ClassVar[list[GuardrailExecutionStage]] = []
    """Stages this validator supports. Empty list means all stages are allowed."""

    def validate_stage(self, stage: GuardrailExecutionStage) -> None:
        """Raise ``ValueError`` if *stage* is not in `supported_stages`.

        Args:
            stage: Requested execution stage.

        Raises:
            ValueError: If `supported_stages` is non-empty and *stage* is absent.
        """
        if self.supported_stages and stage not in self.supported_stages:
            raise ValueError(
                f"{type(self).__name__} does not support stage {stage!r}. "
                f"Supported stages: {[s.value for s in self.supported_stages]}"
            )

    def run(
        self,
        name: str,
        description: str | None,
        enabled_for_evals: bool,
        data: "str | dict[str, Any]",
        stage: GuardrailExecutionStage,
        input_data: "dict[str, Any] | None",
        output_data: "dict[str, Any] | None",
    ) -> GuardrailValidationResult:
        """Execute the guardrail evaluation.

        Called by the ``@guardrail`` decorator at each function invocation.
        Subclasses override this via `BuiltInGuardrailValidator` or
        `CustomGuardrailValidator`.

        Raises:
            NotImplementedError: Always — subclass one of the two ABCs instead.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must subclass BuiltInGuardrailValidator "
            "or CustomGuardrailValidator and implement the required abstract method."
        )


class BuiltInGuardrailValidator(GuardrailValidatorBase, ABC):
    """Base for validators that delegate to the UiPath Guardrails API.

    Subclass this and implement `get_built_in_guardrail()` to create an
    API-backed guardrail validator (e.g. PII detection, prompt injection).

    Example:
        ```python
        class MyValidator(BuiltInGuardrailValidator):
            def get_built_in_guardrail(self, name, description, enabled_for_evals):
                return BuiltInValidatorGuardrail(
                    id=str(uuid4()),
                    name=name,
                    ...
                )
        ```
    """

    @abstractmethod
    def get_built_in_guardrail(
        self,
        name: str,
        description: str | None,
        enabled_for_evals: bool,
    ) -> BuiltInValidatorGuardrail:
        """Build the UiPath API guardrail definition for this validator.

        Args:
            name: Name for the guardrail instance.
            description: Optional description.
            enabled_for_evals: Whether active in evaluation scenarios.

        Returns:
            `BuiltInValidatorGuardrail` ready to be sent to the API.
        """
        ...

    def run(
        self,
        name: str,
        description: str | None,
        enabled_for_evals: bool,
        data: "str | dict[str, Any]",
        stage: GuardrailExecutionStage,
        input_data: "dict[str, Any] | None",
        output_data: "dict[str, Any] | None",
        *,
        attachments: list[GuardrailAttachment] | None = None,
        detection_scope: DetectionScope | None = None,
    ) -> GuardrailValidationResult:
        """Evaluate via the UiPath Guardrails API.

        Lazily initialises the ``UiPath`` client on the first call and reuses
        it for all subsequent invocations.

        Args:
            name: Name for the guardrail instance.
            description: Optional description.
            enabled_for_evals: Whether active in evaluation scenarios.
            data: Primary data being evaluated.
            stage: Current execution stage (PRE or POST).
            input_data: Normalised function input dict, or ``None``.
            output_data: Normalised function output dict, or ``None``.
            attachments: File references the backend may inspect, or ``None`` to say
                nothing about files (the text is evaluated as before). They are
                dropped when the guardrail is scoped to text, and when the service
                rejects them (HTTP 400) the data is evaluated again without them.
                An empty list sent for a guardrail whose scope explicitly includes
                files tells the backend that files apply and there are none.
            detection_scope: The ``appliesTo`` scope to send, replacing any the
                guardrail already carries; ``None`` keeps the backend default.

        Returns:
            The outcome of the guardrail evaluation.
        """
        built_in = with_detection_scope(
            self.get_built_in_guardrail(name, description, enabled_for_evals),
            detection_scope,
        )
        files_apply = scope_includes_files(built_in)
        files_requested = files_apply and (
            detection_scope is not None or _declares_detection_scope(built_in)
        )
        if not hasattr(self, "_uipath"):
            from uipath.platform import UiPath

            self._uipath: Any = UiPath()
        guardrails = self._uipath.guardrails
        if not files_apply or attachments is None:
            return guardrails.evaluate_guardrail(data, built_in)
        if not attachments:
            if files_requested:
                return guardrails.evaluate_guardrail(data, built_in, attachments=[])
            return guardrails.evaluate_guardrail(data, built_in)
        try:
            return guardrails.evaluate_guardrail(
                data, built_in, attachments=list(attachments)
            )
        except EnrichedException as exc:
            if exc.status_code != 400:
                raise
            logger.warning(
                "Guardrail '%s' rejected the attachment references (HTTP 400); "
                "re-evaluating without attachments (%d dropped).",
                name,
                len(attachments),
            )
            logger.debug(
                "Guardrail '%s' dropped the attachment ids %s.",
                name,
                ", ".join(attachment.id for attachment in attachments),
            )
            return guardrails.evaluate_guardrail(data, built_in)


class CustomGuardrailValidator(GuardrailValidatorBase, ABC):
    """Base for validators that run entirely in-process.

    Subclass this and implement `evaluate()` to create a local guardrail
    validator that requires no UiPath API call.

    Example:
        ```python
        class ProfanityValidator(CustomGuardrailValidator):
            BANNED = {"badword"}

            def evaluate(self, data, stage, input_data, output_data):
                text = (input_data or {}).get("message", "")
                if any(w in text.lower() for w in self.BANNED):
                    return GuardrailValidationResult(
                        result=GuardrailValidationResultType.VALIDATION_FAILED,
                        reason="Profanity detected",
                    )
                return GuardrailValidationResult(result=GuardrailValidationResultType.PASSED)
        ```
    """

    @abstractmethod
    def evaluate(
        self,
        data: "str | dict[str, Any]",
        stage: GuardrailExecutionStage,
        input_data: "dict[str, Any] | None",
        output_data: "dict[str, Any] | None",
    ) -> GuardrailValidationResult:
        """Perform local validation without a UiPath API call.

        Return a result with ``VALIDATION_FAILED`` to **trigger** the guardrail
        (causing the configured `GuardrailAction`
        to fire), or ``PASSED`` to let execution continue unchanged.

        Args:
            data: Primary data being evaluated.
            stage: Current execution stage (PRE or POST).
            input_data: Normalised function input dict, or ``None``.
            output_data: Normalised function output dict, or ``None`` at PRE stage.

        Returns:
            `GuardrailValidationResult` —
            return ``VALIDATION_FAILED`` to activate the guardrail,
            ``PASSED`` to allow execution to continue.
        """
        ...

    def run(
        self,
        name: str,
        description: str | None,
        enabled_for_evals: bool,
        data: "str | dict[str, Any]",
        stage: GuardrailExecutionStage,
        input_data: "dict[str, Any] | None",
        output_data: "dict[str, Any] | None",
    ) -> GuardrailValidationResult:
        """Delegate to `evaluate()`."""
        return self.evaluate(data, stage, input_data, output_data)
