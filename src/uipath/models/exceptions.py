from typing import Optional


class IngestionInProgressException(Exception):
    """An exception that is triggered when a search is attempted on an index that is currently undergoing ingestion."""

    def __init__(self, index_name: Optional[str], search_operation: bool = True):
        index_name = index_name or "Unknown index name"
        if search_operation:
            self.message = f"index '{index_name}' cannot be searched during ingestion"
        else:
            self.message = f"index '{index_name}' is currently queued for ingestion"
        super().__init__(self.message)
