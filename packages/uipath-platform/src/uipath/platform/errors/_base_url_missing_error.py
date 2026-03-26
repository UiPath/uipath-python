class BaseUrlMissingError(Exception):
    """Raised when base URL is not configured.

    This exception is raised when attempting to use the SDK without setting
    the base URL via the UIPATH_URL environment variable or through authentication.
    """

    def __init__(
        self,
        message="Authentication required. Please run \033[1muipath auth\033[22m or set the base URL via the UIPATH_URL environment variable.",
    ):
        self.message = message
        super().__init__(self.message)
