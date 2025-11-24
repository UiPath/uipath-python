class FolderNotFoundException(Exception):
    """Raised when a folder cannot be found.

    This exception is raised when attempting to access a folder that does not exist
    in the UiPath Orchestrator.
    """

    def __init__(
        self,
        folder_name,
    ):
        self.message = f"Folder {folder_name} not found."
        super().__init__(self.message)
