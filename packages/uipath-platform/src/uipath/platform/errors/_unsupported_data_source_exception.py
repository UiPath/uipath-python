from typing import Optional


class UnsupportedDataSourceException(Exception):
    """Raised when an operation is attempted on an unsupported data source type.

    This exception is raised when attempting to use an operation that only supports
    specific data source types (e.g., Orchestrator Storage Bucket) with an incompatible
    data source.
    """

    def __init__(self, operation: str, data_source_type: Optional[str] = None):
        if data_source_type:
            message = f"Operation '{operation}' is not supported for data source type: {data_source_type}. Only Orchestrator Storage Bucket data sources are supported."
        else:
            message = f"Operation '{operation}' requires an Orchestrator Storage Bucket data source."
        super().__init__(message)
