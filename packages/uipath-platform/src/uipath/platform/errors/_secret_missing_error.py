class SecretMissingError(Exception):
    """Raised when access token is not configured.

    This exception is raised when attempting to use the SDK without setting
    the access token via the UIPATH_ACCESS_TOKEN environment variable or through authentication.
    """

    def __init__(
        self,
        message="Authentication required. Please run \033[1muipath auth\033[22m or set the UIPATH_ACCESS_TOKEN environment variable to a valid access token.",
    ):
        self.message = message
        super().__init__(self.message)
