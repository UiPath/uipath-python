class AppNotFoundError(Exception):
    """Raised when an Action Center app cannot be found by name.

    The app is either not deployed in the tenant, or not deployed in the
    folder the caller asked for.
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)
