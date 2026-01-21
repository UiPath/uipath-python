class OperationFailedException(Exception):
    """Raised when attempting to get results from a failed operation.

    This exception is raised when attempting to retrieve results from operation
    that failed to complete successfully.
    """

    def __init__(
        self,
        operation_id: str,
        status: str,
        error: str,
        operation_name: str = "Operation",
    ):
        self.operation_id = operation_id
        self.status = status
        self.error = error
        self.message = f"{operation_name} '{operation_id}' failed with status: {status} error: {error}"
        super().__init__(self.message)
