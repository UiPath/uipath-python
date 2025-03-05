from dataclasses import dataclass
from typing import Any, Optional

from ._endpoint import Endpoint


@dataclass
class RequestSpec:
    """
    A specification for an HTTP request.
    """

    method: str
    endpoint: Endpoint
    params: Optional[dict[str, Any]] = None
    content: Optional[Any] = None
