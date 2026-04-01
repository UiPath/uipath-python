"""Abstract base classes for guardrail validators."""

from abc import ABC, abstractmethod
from typing import Any, ClassVar

from uipath.core.guardrails import GuardrailValidationResult

from uipath.platform.guardrails.guardrails import BuiltInValidatorGuardrail

from .._enums import GuardrailExecutionStage


class GuardrailValidatorBase:
    """Root base class for guardrail validators.

    Concrete validators should subclass either
    :class:`BuiltInGuardrailValidator` (for UiPath API-backed validation)
    or :class:`CustomGuardrailValidator` (for in-process Python validation).
    """

    supported_stages: ClassVar[list[GuardrailExecutionStage]] = []
    """Stages this validator supports. Empty list means all stages are allowed."""

    def validate_stage(self, stage: GuardrailExecutionStage) -> None:
        """Raise ``ValueError`` if *stage* is not in :attr:`supported_stages`.

        Args:
            stage: Requested execution stage.

        Raises:
            ValueError: If :attr:`supported_stages` is non-empty and *stage* is absent.
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
        Subclasses override this via :class:`BuiltInGuardrailValidator` or
        :class:`CustomGuardrailValidator`.

        Raises:
            NotImplementedError: Always — subclass one of the two ABCs instead.
        """
        raise NotImplementedError(
            f"{type(self).__name__} must subclass BuiltInGuardrailValidator "
            "or CustomGuardrailValidator and implement the required abstract method."
        )


class BuiltInGuardrailValidator(GuardrailValidatorBase, ABC):
    """Base for validators that delegate to the UiPath Guardrails API.

    Subclass this and implement :meth:`get_built_in_guardrail` to create an
    API-backed guardrail validator (e.g. PII detection, prompt injection).

    Example::

        class MyValidator(BuiltInGuardrailValidator):
            def get_built_in_guardrail(self, name, description, enabled_for_evals):
                return BuiltInValidatorGuardrail(
                    id=str(uuid4()),
                    name=name,
                    ...
                )
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
            :class:`BuiltInValidatorGuardrail` ready to be sent to the API.
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
        """Evaluate via the UiPath Guardrails API.

        Lazily initialises the ``UiPath`` client on the first call and reuses
        it for all subsequent invocations.
        """
        built_in = self.get_built_in_guardrail(name, description, enabled_for_evals)
        if not hasattr(self, "_uipath"):
            from uipath.platform import UiPath

            self._uipath: Any = UiPath()
        return self._uipath.guardrails.evaluate_guardrail(data, built_in)


class CustomGuardrailValidator(GuardrailValidatorBase, ABC):
    """Base for validators that run entirely in-process.

    Subclass this and implement :meth:`evaluate` to create a local guardrail
    validator that requires no UiPath API call.

    Example::

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
        (causing the configured :class:`~uipath.platform.guardrails.decorators.GuardrailAction`
        to fire), or ``PASSED`` to let execution continue unchanged.

        Args:
            data: Primary data being evaluated.
            stage: Current execution stage (PRE or POST).
            input_data: Normalised function input dict, or ``None``.
            output_data: Normalised function output dict, or ``None`` at PRE stage.

        Returns:
            :class:`~uipath.core.guardrails.GuardrailValidationResult` —
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
        """Delegate to :meth:`evaluate`."""
        return self.evaluate(data, stage, input_data, output_data)
