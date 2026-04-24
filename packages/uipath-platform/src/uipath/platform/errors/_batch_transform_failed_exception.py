class BatchTransformFailedException(Exception):
    """Raised when a batch transform has failed.

    This exception is raised when a batch transform task has completed
    with a failed status, as opposed to still being in progress.
    """

    def __init__(self, batch_transform_id: str):
        self.message = f"Batch transform '{batch_transform_id}' failed."
        super().__init__(self.message)
