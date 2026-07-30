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
    Configurations``; this validator references it by its validator name and
    (recommended) Integration Service connection id.

    Supported at all stages — BYO validator capabilities are connector-defined
    and cannot be known statically, so no stage restriction is applied here.
    Configuring a scope or stage the connector does not support surfaces as a
    ``PROVIDER_ERROR`` at evaluation time.

    Example::

        from uipath.platform.guardrails.decorators import (
            BlockAction,
            ByoValidator,
            guardrail,
        )

        byog_harmful_content = ByoValidator(
            "byog-harmful-content",
            connection_id="24887687-6ed1-4fe2-9b87-087ffb232682",
        )

        @guardrail(validator=byog_harmful_content, action=BlockAction())
        def summarize(text: str) -> str:
            ...

    Args:
        validator_name: The BYOG configuration's validator name
            (``byoValidatorName``), as shown in Admin -> AI Trust Layer ->
            Guardrails Configurations.
        connection_id: Optional Integration Service connection id backing the
            BYOG configuration. Strongly recommended: validator names are only
            unique per connection, so omitting it lets the server pick the
            first configuration matching the name.
        parameters: Optional list of validator parameters. BYO parameter
            schemas are connector-defined, so values are passed through as-is.

    Raises:
        ValueError: If *validator_name* is empty or whitespace.
    """

    def __init__(
        self,
        validator_name: str,
        *,
        connection_id: str | None = None,
        parameters: Sequence[ValidatorParameter] | None = None,
    ) -> None:
        """Initialize ByoValidator with a BYOG configuration reference."""
        if not validator_name or not validator_name.strip():
            raise ValueError("validator_name must be a non-empty string")
        self.validator_name = validator_name
        self.connection_id = connection_id
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
            configuration via ``byoValidatorName``/``byoConnectionId``.
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
            byo_connection_id=self.connection_id,
        )
