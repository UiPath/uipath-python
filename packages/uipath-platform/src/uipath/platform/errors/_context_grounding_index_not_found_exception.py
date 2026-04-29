from typing import Optional


class ContextGroundingIndexNotFoundError(Exception):
    """Raised when a context grounding index cannot be resolved by name."""

    def __init__(self, index_name: Optional[str] = None):
        self.index_name = index_name
        if index_name:
            self.message = f"ContextGroundingIndex '{index_name}' not found"
        else:
            self.message = "ContextGroundingIndex not found"
        super().__init__(self.message)
