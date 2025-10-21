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
