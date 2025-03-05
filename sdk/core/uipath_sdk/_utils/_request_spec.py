from dataclasses import dataclass
from typing import Any, Optional, Union

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
    json: Optional[Any] = None
    headers: Optional[dict[str, Any]] = None
    data: Optional[Any] = None
    timeout: Optional[Union[int, float]] = None
