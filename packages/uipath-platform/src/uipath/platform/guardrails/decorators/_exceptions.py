"""Exceptions for guardrail decorators."""


class GuardrailBlockException(Exception):
    """Raised by BlockAction when a guardrail blocks execution.

    Framework adapters (e.g. LangChain) should catch this and convert it to
    their own runtime exception type at the outermost wrapper boundary.

    Args:
        title: Brief title for the block event.
        detail: Detailed reason for the block.
    """

    def __init__(self, title: str, detail: str) -> None:
        self.title = title
        self.detail = detail
        super().__init__(f"{title}: {detail}")
