class ExtractionNotCompleteException(Exception):
    """Raised when attempting to get results from an incomplete IXP extraction.

    This exception is raised when attempting to retrieve results from an IXP
    extraction operation that has not yet completed successfully.
    """

    def __init__(self, operation_id: str, status: str):
        self.operation_id = operation_id
        self.status = status
        self.message = (
            f"IXP extraction '{operation_id}' is not complete. Current status: {status}"
        )
        super().__init__(self.message)
