class OperationNotCompleteException(Exception):
    """Raised when attempting to get results from an incomplete operation.

    This exception is raised when attempting to retrieve results from operation
    that has not yet completed successfully.
    """

    def __init__(
        self, operation_id: str, status: str, operation_name: str = "Operation"
    ):
        self.operation_id = operation_id
        self.status = status
        self.message = f"{operation_name} '{operation_id}' is not complete. Current status: {status}"
        super().__init__(self.message)
