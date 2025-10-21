from typing import Any


class Endpoint(str):
    """A string subclass representing a normalized API endpoint path.

    This class ensures consistent endpoint formatting by:
    - Adding a leading slash if missing
    - Removing trailing slashes (except for root '/')
    - Stripping query parameters

    The class supports string formatting for dynamic path parameters.

    Examples:
        >>> endpoint = Endpoint("/api/v1/users/{id}")
        >>> endpoint.format(id=123)
        '/api/v1/users/123'

        >>> endpoint = Endpoint("projects")
        >>> str(endpoint)
        '/projects'

    Args:
        endpoint (str): The endpoint path to normalize. May include format placeholders
            for dynamic values (e.g. "/users/{id}").

    Raises:
        ValueError: If format() is called with None or empty string arguments.
    """

    def __new__(cls, endpoint: str) -> "Endpoint":
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"

        if endpoint != "/" and endpoint.endswith("/"):
            endpoint = endpoint[:-1]

        endpoint = endpoint.split("?")[0]

        return super().__new__(cls, endpoint)

    def format(self, *args: Any, **kwargs: Any) -> str:
        """Formats the endpoint with the given arguments."""
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
        """Extracts and returns the service name from the endpoint path.

        The service name is expected to be the first path segment after the leading slash,
        with any underscores removed.

        Examples:
            >>> endpoint = Endpoint("/cloud_/projects")
            >>> endpoint.service
            'cloud'

            >>> endpoint = Endpoint("/automation_hub_/assets")
            >>> endpoint.service
            'automationhub'

        Returns:
            str: The service name with underscores removed.
        """
        return self.split("/")[1].replace("_", "")
