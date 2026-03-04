from httpx import HTTPStatusError


class EnrichedException(Exception):
    """Enriched HTTP error with detailed request/response information.

    This exception wraps HTTPStatusError and provides additional context about
    the failed HTTP request, including URL, method, status code, and response content.
    """

    def __init__(self, error: HTTPStatusError) -> None:
        # Extract the relevant details from the HTTPStatusError
        self.status_code = error.response.status_code if error.response else "Unknown"
        self.url = str(error.request.url) if error.request else "Unknown"
        self.http_method = (
            error.request.method
            if error.request and error.request.method
            else "Unknown"
        )
        max_content_length = 200
        if error.response and error.response.content:
            content = error.response.content.decode("utf-8")
            if len(content) > max_content_length:
                self.response_content = content[:max_content_length] + "... (truncated)"
            else:
                self.response_content = content
        else:
            self.response_content = "No content"

        enriched_message = (
            f"\nRequest URL: {self.url}"
            f"\nHTTP Method: {self.http_method}"
            f"\nStatus Code: {self.status_code}"
            f"\nResponse Content: {self.response_content}"
        )

        # Initialize the parent Exception class with the formatted message
        super().__init__(enriched_message)
