from httpx import ReadTimeout, Request


class GuardrailValidationTimeoutError(ReadTimeout):
    """Raised when the guardrails service does not answer a validation in time.

    The request reached the service and is not sent again. It stays an
    ``httpx.ReadTimeout``, which is what such a call raised before, so existing
    handlers keep catching it.
    """

    def __init__(
        self,
        guardrail_name: str,
        timeout_seconds: float,
        *,
        request: Request | None = None,
    ) -> None:
        self.guardrail_name = guardrail_name
        self.timeout_seconds = timeout_seconds
        self.message = (
            f"The guardrails service did not answer within {timeout_seconds:g} s "
            f"while validating guardrail '{guardrail_name}'."
        )
        super().__init__(self.message, request=request)
