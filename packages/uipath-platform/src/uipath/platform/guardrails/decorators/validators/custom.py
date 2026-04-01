"""Custom (rule-based) guardrail validator."""

import inspect
from typing import Any, Callable

from uipath.core.guardrails import (
    GuardrailValidationResult,
    GuardrailValidationResultType,
)

from .._enums import GuardrailExecutionStage
from ._base import CustomGuardrailValidator

RuleFunction = (
    Callable[[dict[str, Any]], bool] | Callable[[dict[str, Any], dict[str, Any]], bool]
)
"""Type alias for custom rule functions passed to :class:`CustomValidator`.

The rule must return ``True`` to **trigger** the guardrail (i.e. signal a
violation that causes the configured action to fire), or ``False`` to let
execution continue unchanged.

It accepts either one parameter (the input or output dict) or two parameters
(input dict, output dict — POST stage only).

Examples::

    # Triggered when "donkey" appears in the joke argument
    CustomValidator(lambda args: "donkey" in args.get("joke", "").lower())

    # Triggered when the output joke exceeds 500 characters
    CustomValidator(lambda args: len(args.get("joke", "")) > 500)

    # Two-parameter form: triggered at POST when output contains input keyword
    CustomValidator(lambda inp, out: inp.get("topic", "") in out.get("joke", ""))
"""


class CustomValidator(CustomGuardrailValidator):
    """Validate function input/output using a local Python rule function.

    No UiPath API call is made. Applicable at any stage.

    The *rule* is called with the collected parameter dict (PRE stage) or the
    serialised return-value dict (POST stage).  It must return ``True`` to
    **activate** the guardrail — i.e. to signal a violation and invoke the
    configured :class:`~uipath.platform.guardrails.decorators.GuardrailAction`.
    Return ``False`` (or any falsy value) to let execution continue unchanged.

    Args:
        rule: A :data:`RuleFunction` that returns ``True`` to trigger the
            guardrail.  Must accept 1 or 2 parameters.

    Raises:
        ValueError: If *rule* is not callable or has an unsupported parameter count.
    """

    def __init__(self, rule: RuleFunction) -> None:
        """Initialize CustomValidator with a rule callable."""
        if not callable(rule):
            raise ValueError(f"rule must be callable, got {type(rule)}")
        sig = inspect.signature(rule)
        param_count = len(sig.parameters)
        if param_count not in (1, 2):
            raise ValueError(f"rule must have 1 or 2 parameters, got {param_count}")
        self.rule = rule
        self._param_count = param_count

    def evaluate(
        self,
        data: str | dict[str, Any],
        stage: GuardrailExecutionStage,
        input_data: dict[str, Any] | None,
        output_data: dict[str, Any] | None,
    ) -> GuardrailValidationResult:
        """Run the rule against the collected input or output dict.

        The rule receives the PRE parameter dict or POST return-value dict and
        must return ``True`` to **trigger** the guardrail (VALIDATION_FAILED),
        or ``False`` to pass.

        Args:
            data: Unused; the rule operates on *input_data* or *output_data*.
            stage: Current stage (PRE or POST).
            input_data: Collected function input dict.
            output_data: Collected function output dict, or ``None`` at PRE stage.

        Returns:
            :class:`~uipath.core.guardrails.GuardrailValidationResult` —
            ``VALIDATION_FAILED`` when the rule returns ``True`` (guardrail
            triggered), ``PASSED`` otherwise.
        """
        try:
            if self._param_count == 2:
                if input_data is None or output_data is None:
                    return GuardrailValidationResult(
                        result=GuardrailValidationResultType.PASSED,
                        reason="Two-parameter rule skipped: input or output data unavailable",
                    )
                violation = self.rule(input_data, output_data)  # type: ignore[call-arg]
            else:
                target = (
                    input_data if stage == GuardrailExecutionStage.PRE else output_data
                )
                if target is None:
                    return GuardrailValidationResult(
                        result=GuardrailValidationResultType.PASSED,
                        reason="Rule skipped: data unavailable at this stage",
                    )
                violation = self.rule(target)  # type: ignore[call-arg]
        except Exception as exc:
            return GuardrailValidationResult(
                result=GuardrailValidationResultType.PASSED,
                reason=f"Rule raised exception: {exc}",
            )

        if violation:
            return GuardrailValidationResult(
                result=GuardrailValidationResultType.VALIDATION_FAILED,
                reason="Rule detected violation",
            )
        return GuardrailValidationResult(
            result=GuardrailValidationResultType.PASSED,
            reason="Rule passed",
        )
