class BaseUrlMissingError(Exception):
    def __init__(
        self,
        message="Authentication required. Please run \033[1muipath auth\033[22m or set the base URL via the UIPATH_URL environment variable.",
    ):
        self.message = message
        super().__init__(self.message)


class SecretMissingError(Exception):
    def __init__(
        self,
        message="Authentication required. Please run \033[1muipath auth\033[22m or set the UIPATH_ACCESS_TOKEN environment variable to a valid access token.",
    ):
        self.message = message
        super().__init__(self.message)


class PaginationLimitError(Exception):
    """Raised when pagination limit is exceeded.

    The SDK limits auto-pagination to prevent performance issues with
    deep OFFSET queries. Use filters or manual pagination to retrieve
    additional results.
    """

    @staticmethod
    def create(
        max_pages: int,
        items_per_page: int,
        method_name: str,
        filter_example: str = "",
    ) -> "PaginationLimitError":
        """Create PaginationLimitError for any pagination method.

        Args:
            max_pages: Maximum number of pages allowed
            items_per_page: Number of items per page
            method_name: Name of the method that hit the limit
            filter_example: Optional example filter to narrow results (e.g., 'name="my-bucket"')

        Returns:
            PaginationLimitError with formatted message
        """
        total_items = max_pages * items_per_page

        # Build message with optional filter example
        message_parts = [
            f"Pagination limit reached: {max_pages} pages "
            f"({total_items} items) retrieved, but more data may be available."
        ]

        if filter_example:
            message_parts.extend(
                [
                    "To retrieve additional results:",
                    "  1. Add filters to narrow your query:",
                    f"     {method_name}({filter_example})",
                    "  2. Process results in smaller batches using appropriate filters.",
                ]
            )
        else:
            message_parts.append(
                "To retrieve additional results, add filters to narrow your query."
            )

        message_parts.append(
            "See: https://docs.uipath.com/orchestrator/automation-cloud/latest/api-guide/building-api-requests"
        )

        message = "\n".join(message_parts)
        return PaginationLimitError(message)
