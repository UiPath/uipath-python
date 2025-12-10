"""UiPath Platform Errors.

This module contains all exception classes used by the UiPath Platform SDK.

Available exceptions:
- BaseUrlMissingError: Raised when base URL is not configured
- SecretMissingError: Raised when access token is not configured
- FolderNotFoundException: Raised when a folder cannot be found
- UnsupportedDataSourceException: Raised when an operation is attempted on an unsupported data source type
- IngestionInProgressException: Raised when a search is attempted on an index during ingestion
- BatchTransformNotCompleteException: Raised when attempting to get results from an incomplete batch transform
- EnrichedException: Enriched HTTP error with detailed request/response information
"""

from ._base_url_missing_error import BaseUrlMissingError
from ._batch_transform_not_complete_exception import BatchTransformNotCompleteException
from ._enriched_exception import EnrichedException
from ._folder_not_found_exception import FolderNotFoundException
from ._ingestion_in_progress_exception import IngestionInProgressException
from ._secret_missing_error import SecretMissingError
from ._unsupported_data_source_exception import UnsupportedDataSourceException

__all__ = [
    "BaseUrlMissingError",
    "BatchTransformNotCompleteException",
    "EnrichedException",
    "FolderNotFoundException",
    "IngestionInProgressException",
    "SecretMissingError",
    "UnsupportedDataSourceException",
]
