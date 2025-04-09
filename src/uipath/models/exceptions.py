class IngestionInProgressException(Exception):
    """An exception that is triggered when a search is attempted on an index that is currently undergoing ingestion."""

    def __init__(self, index_name):
        self.message = f"index {index_name} cannot be searched during ingestion"
        super().__init__(self.message)
