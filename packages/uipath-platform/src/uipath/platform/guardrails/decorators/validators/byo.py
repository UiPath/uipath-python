"""Bring Your Own Guardrail (BYOG) validator."""

from typing import Sequence
from uuid import uuid4

from uipath.platform.guardrails.guardrails import (
    BYO_VALIDATOR_TYPE,
    BuiltInValidatorGuardrail,
    ValidatorParameter,
)

from ._base import BuiltInGuardrailValidator


class ByoValidator(BuiltInGuardrailValidator):
    """Validate data through a Bring Your Own Guardrail (BYOG) configuration.

    BYOG lets an organization plug its own safety validator (e.g. a customer
    Azure Content Safety subscription, a vendor connector, or a custom
    Integration Service connector) into UiPath guardrails. An admin first
    creates the configuration under ``Admin -> AI Trust Layer -> Guardrails
    Configurations``; this validator references it purely by its validator
    name, which is unique per tenant. The Integration Service connection to
    use is resolved server-side from the configuration, so an admin rebind is
    always honored.

    Supported at all stages — BYO validator capabilities are connector-defined
    and cannot be known statically, so no stage restriction is applied here.

    Example::

        from uipath.platform.guardrails.decorators import (
            BlockAction,
            ByoValidator,
            guardrail,
        )

        byog_harmful_content = ByoValidator("my-harmful-content-guardrail")

        @guardrail(validator=byog_harmful_content, action=BlockAction())
        def summarize(text: str) -> str:
            ...

    Args:
        validator_name: The BYOG configuration's validator name
            (``byoValidatorName``), as shown in Admin -> AI Trust Layer ->
            Guardrails Configurations. Unique per tenant.
        parameters: Optional list of validator parameters. BYO parameter
            schemas are connector-defined, so values are passed through as-is.

    Raises:
        ValueError: If *validator_name* is empty or whitespace.
    """

    def __init__(
        self,
        validator_name: str,
        *,
        parameters: Sequence[ValidatorParameter] | None = None,
    ) -> None:
        """Initialize ByoValidator with a BYOG configuration reference."""
        if not validator_name or not validator_name.strip():
            raise ValueError("validator_name must be a non-empty string")
        self.validator_name = validator_name
        self.parameters = list(parameters or [])

    def get_built_in_guardrail(
        self,
        name: str,
        description: str | None,
        enabled_for_evals: bool,
    ) -> BuiltInValidatorGuardrail:
        """Build a BYOG :class:`BuiltInValidatorGuardrail`.

        Args:
            name: Name for the guardrail.
            description: Optional description.
            enabled_for_evals: Whether active in evaluation scenarios.

        Returns:
            Configured :class:`BuiltInValidatorGuardrail` referencing the BYOG
            configuration via ``byoValidatorName``.
        """
        return BuiltInValidatorGuardrail(
            id=str(uuid4()),
            name=name,
            description=description
            or f"Bring Your Own Guardrail validation '{self.validator_name}'",
            enabled_for_evals=enabled_for_evals,
            guardrail_type="builtInValidator",
            validator_type=BYO_VALIDATOR_TYPE,
            validator_parameters=self.parameters,
            byo_validator_name=self.validator_name,
        )
