"""Module for process invocation handling for interrupt job scenarios."""

from typing import Any, Dict, Optional

from pydantic import BaseModel


class InvokeProcess(BaseModel):
    """Class to handle job trigger interrupt scenarios."""

    name: str
    input_arguments: Optional[Dict[str, Any]]
