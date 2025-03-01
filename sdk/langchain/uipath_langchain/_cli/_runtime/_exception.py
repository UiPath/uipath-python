from typing import Optional

from uipath_sdk._cli._runtime._contracts import ErrorCategory, UiPathRuntimeError


class LangGraphRuntimeError(UiPathRuntimeError):
    """Custom exception for LangGraph runtime errors with structured error information."""

    def __init__(
        self,
        code: str,
        title: str,
        detail: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        status: Optional[int] = None,
    ):
        super().__init__(code, title, detail, category, status, prefix="LANGGRAPH")
