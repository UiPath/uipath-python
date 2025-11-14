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
        current_skip: int,
        filter_example: str,
    ) -> "PaginationLimitError":
        """Create a PaginationLimitError with a standardized message.

        Args:
            max_pages: Maximum number of pages allowed
            items_per_page: Number of items per page
            method_name: Name of the method that hit the limit
            current_skip: Current skip value for manual pagination
            filter_example: Example filter expression for the user

        Returns:
            PaginationLimitError with formatted message
        """
        message = (
            f"Pagination limit reached: {max_pages} pages "
            f"({max_pages * items_per_page} items) retrieved. "
            f"More results may be available. To retrieve them:\n"
            f"  1. Add filters to narrow results: "
            f'{method_name}(filter="{filter_example}")\n'
            f"  2. Use manual pagination: "
            f"{method_name}(skip={current_skip}, top={items_per_page})\n"
            f"See: https://docs.uipath.com/orchestrator/automation-cloud/latest/api-guide/building-api-requests"
        )
        return PaginationLimitError(message)
