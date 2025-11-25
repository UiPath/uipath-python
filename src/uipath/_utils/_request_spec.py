from dataclasses import dataclass, field
from typing import Any, Union

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
    params: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, Any] = field(default_factory=dict)
    content: Any | None = None
    json: Any | None = None
    data: Any | None = None
    timeout: Union[int, float] | None = None
