from dataclasses import dataclass
from typing import Any, Optional, Union

from ._endpoint import Endpoint


@dataclass
class RequestSpec:
    """Encapsulates the configuration for making an HTTP request.

    This class contains all necessary parameters to construct and send an HTTP request,
    including the HTTP method, endpoint, query parameters, headers, and various forms
    of request body data (content, JSON, form data).
    """

    method: str
    endpoint: Endpoint
    params: Optional[dict[str, Any]] = None
    content: Optional[Any] = None
    json: Optional[Any] = None
    headers: Optional[dict[str, Any]] = None
    data: Optional[Any] = None
    timeout: Optional[Union[int, float]] = None
