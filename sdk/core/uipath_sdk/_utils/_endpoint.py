from typing import Any


class Endpoint(str):
    """
    This class represents an API endpoint.
    It ensures the endpoint:
      - Starts with a slash.
      - Does not end with a slash (unless it's the root).
      - Has no query parameters.

    It supports standard string formatting for dynamic endpoints.

    Args:
        endpoint: The endpoint to parse, which may include placeholders.
    """

    def __new__(cls, endpoint: str) -> "Endpoint":
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"

        if endpoint != "/" and endpoint.endswith("/"):
            endpoint = endpoint[:-1]

        endpoint = endpoint.split("?")[0]

        return super().__new__(cls, endpoint)

    def format(self, *args: Any, **kwargs: Any) -> str:
        """
        Formats the endpoint with the given arguments.
        """
        for index, arg in enumerate(args):
            if not self._is_valid_value(arg):
                raise ValueError(f"Positional argument `{index}` is `{arg}`.")

        for key, value in kwargs.items():
            if not self._is_valid_value(value):
                raise ValueError(f"Keyword argument `{key}` is `{value}`.")

        return super().format(*args, **kwargs)

    def __repr__(self) -> str:
        return f"Endpoint({super().__str__()!r})"

    def _is_valid_value(self, value: Any) -> bool:
        return value is not None and value != ""

    @property
    def service(self) -> str:
        """
        Returns the service name from the endpoint.
        Assumes the endpoint is in the format `/service_/path`.
        """
        return self.split("/")[1].replace("_", "")
