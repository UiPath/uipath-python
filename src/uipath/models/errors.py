class BaseUrlMissingError(Exception):
    def __init__(
        self,
        message="Authentication required. Please run \033[1muipath auth\033[22m.",
    ):
        self.message = message
        super().__init__(self.message)


class SecretMissingError(Exception):
    def __init__(
        self,
        message="Authentication required. Please run \033[1muipath auth\033[22m.",
    ):
        self.message = message
        super().__init__(self.message)
