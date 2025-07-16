from typing import Optional

from httpx import HTTPStatusError


class IngestionInProgressException(Exception):
    """An exception that is triggered when a search is attempted on an index that is currently undergoing ingestion."""

    def __init__(self, index_name: Optional[str], search_operation: bool = True):
        index_name = index_name or "Unknown index name"
        if search_operation:
            self.message = f"index '{index_name}' cannot be searched during ingestion"
        else:
            self.message = f"index '{index_name}' is currently queued for ingestion"
        super().__init__(self.message)


class EnrichedException(Exception):
    def __init__(self, error: HTTPStatusError) -> None:
        # Extract the relevant details from the HTTPStatusError
        status_code = error.response.status_code if error.response else "Unknown"
        url = str(error.request.url) if error.request else "Unknown"
        response_content = (
            error.response.content.decode("utf-8")
            if error.response and error.response.content
            else "No content"
        )

        enriched_message = (
            f"\nRequest URL: {url}"
            f"\nStatus Code: {status_code}"
            f"\nResponse Content: {response_content}"
        )

        # Initialize the parent Exception class with the formatted message
        super().__init__(enriched_message)
