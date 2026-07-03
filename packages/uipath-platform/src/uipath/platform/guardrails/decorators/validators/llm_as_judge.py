"""LLM-as-judge guardrail validator."""

from typing import Any, Sequence
from uuid import uuid4

from uipath.platform._guardrails_service import (
    BuiltInValidatorGuardrail,
    EnumParameterValue,
    NumberParameterValue,
    TextListParameterValue,
    TextParameterValue,
)

from ._base import BuiltInGuardrailValidator

# Threshold scale matches the backend OOTB catalog: any float in [0, 6], default 2
# (the catalog's UI step of 2 is only a slider increment; the server accepts any
# value in range). HIGHER = more lenient (only flag clear violations), LOWER = stricter.
_THRESHOLD_MIN = 0.0
_THRESHOLD_MAX = 6.0
_THRESHOLD_DEFAULT = 2.0

# Input limits mirror the backend OOTB catalog / LlmAsJudgeProviderApi; keep in sync.
_MAX_GUARDRAIL_TEXT_LENGTH = 4000
_MAX_EXAMPLE_LENGTH = 1000
_MAX_EXAMPLES_PER_LIST = 2


class LLMAsJudgeValidator(BuiltInGuardrailValidator):
    """Validate content against a natural-language rule via an LLM judge.

    The customer expresses a rule in natural language (``guardrail_text``) and picks a
    judge model; a judge LLM decides whether the evaluated payload complies. Works at
    any scope/stage the ``@guardrail`` decorator wraps (scope is implicit in the
    decorated target; ``supported_stages`` is left as the default empty list, which
    means all stages are allowed — both PRE and POST).

    Args:
        guardrail_text: The natural-language rule the judge evaluates against
            (at most 4000 characters).
        model: The judge model to use (a model id supported by LLM Gateway).
        positive_examples: Optional example payloads that comply with the rule
            (at most 2 entries, each at most 1000 characters).
        negative_examples: Optional example payloads that violate the rule
            (at most 2 entries, each at most 1000 characters).
        threshold: Strictness on a 0-6 scale (default 2); higher is more lenient.

    Raises:
        ValueError: If ``guardrail_text``/``model`` are empty, ``threshold`` is
            outside [0, 6], ``guardrail_text`` exceeds 4000 characters, either example
            list has more than 2 entries, or any example exceeds 1000 characters.
    """

    def __init__(
        self,
        guardrail_text: str,
        model: str,
        *,
        positive_examples: Sequence[str] | None = None,
        negative_examples: Sequence[str] | None = None,
        threshold: float = _THRESHOLD_DEFAULT,
    ) -> None:
        """Initialize LLMAsJudgeValidator with the rule, judge model, and options."""
        if not guardrail_text or not guardrail_text.strip():
            raise ValueError("guardrail_text must be a non-empty string")
        if not model or not model.strip():
            raise ValueError("model must be a non-empty string")
        if not _THRESHOLD_MIN <= threshold <= _THRESHOLD_MAX:
            raise ValueError(
                f"threshold must be between {_THRESHOLD_MIN} and {_THRESHOLD_MAX}, "
                f"got {threshold}"
            )
        if len(guardrail_text) > _MAX_GUARDRAIL_TEXT_LENGTH:
            raise ValueError(
                f"guardrail_text exceeds the {_MAX_GUARDRAIL_TEXT_LENGTH}-character "
                f"limit (got {len(guardrail_text)})"
            )
        positive_examples = list(positive_examples or [])
        negative_examples = list(negative_examples or [])
        for label, examples in (
            ("positive_examples", positive_examples),
            ("negative_examples", negative_examples),
        ):
            if len(examples) > _MAX_EXAMPLES_PER_LIST:
                raise ValueError(
                    f"{label} allows at most {_MAX_EXAMPLES_PER_LIST} examples "
                    f"(got {len(examples)})"
                )
            if any(len(e) > _MAX_EXAMPLE_LENGTH for e in examples):
                raise ValueError(
                    f"each {label} entry must be at most {_MAX_EXAMPLE_LENGTH} characters"
                )
        self.guardrail_text = guardrail_text
        self.model = model
        self.positive_examples = positive_examples
        self.negative_examples = negative_examples
        self.threshold = threshold

    def get_built_in_guardrail(
        self,
        name: str,
        description: str | None,
        enabled_for_evals: bool,
    ) -> BuiltInValidatorGuardrail:
        """Build an LLM-as-judge :class:`BuiltInValidatorGuardrail`.

        Args:
            name: Name for the guardrail.
            description: Optional description.
            enabled_for_evals: Whether active in evaluation scenarios.

        Returns:
            Configured :class:`BuiltInValidatorGuardrail` for llm_as_judge.
        """
        validator_parameters: list[Any] = [
            TextParameterValue(
                parameter_type="text",
                id="guardrailText",
                value=self.guardrail_text,
            ),
            EnumParameterValue(
                parameter_type="enum",
                id="model",
                value=self.model,
            ),
            NumberParameterValue(
                parameter_type="number",
                id="threshold",
                value=self.threshold,
            ),
        ]
        if self.positive_examples:
            validator_parameters.append(
                TextListParameterValue(
                    parameter_type="text-list",
                    id="positiveExamples",
                    value=self.positive_examples,
                )
            )
        if self.negative_examples:
            validator_parameters.append(
                TextListParameterValue(
                    parameter_type="text-list",
                    id="negativeExamples",
                    value=self.negative_examples,
                )
            )

        return BuiltInValidatorGuardrail(
            id=str(uuid4()),
            name=name,
            description=description or "LLM-as-judge evaluation",
            enabled_for_evals=enabled_for_evals,
            guardrail_type="builtInValidator",
            validator_type="llm_as_judge",
            validator_parameters=validator_parameters,
        )
