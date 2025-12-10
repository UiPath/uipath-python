class BatchTransformNotCompleteException(Exception):
    """Raised when attempting to get results from an incomplete batch transform.

    This exception is raised when attempting to download results from a batch
    transform task that has not yet completed successfully.
    """

    def __init__(self, batch_transform_id: str, status: str):
        self.message = (
            f"Batch transform '{batch_transform_id}' is not complete. "
            f"Current status: {status}"
        )
        super().__init__(self.message)
