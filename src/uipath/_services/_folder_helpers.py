from typing import Optional

from .folder_service import FolderService


def resolve_folder_key(
    folder_key: Optional[str],
    folder_path: Optional[str],
    folders_service: FolderService,
    context_folder_key: Optional[str] = None,
    context_folder_path: Optional[str] = None,
) -> str:
    """Resolve folder key from provided parameters or instance context.

    Args:
        folder_key: Optional folder key to use directly
        folder_path: Optional folder path to resolve to a key
        folders_service: FolderService instance to resolve folder paths
        context_folder_key: Optional instance-level folder key fallback
        context_folder_path: Optional instance-level folder path fallback

    Returns:
        The resolved folder key

    Raises:
        ValueError: If folder key cannot be resolved
    """
    if folder_key is not None:
        return folder_key

    if folder_path is not None:
        return folders_service.retrieve_folder_key(folder_path=folder_path)

    if context_folder_key is not None:
        return context_folder_key

    if context_folder_path is not None:
        return folders_service.retrieve_folder_key(folder_path=context_folder_path)

    raise ValueError("Failed to resolve folder key")


async def resolve_folder_key_async(
    folder_key: Optional[str],
    folder_path: Optional[str],
    folders_service: FolderService,
    context_folder_key: Optional[str] = None,
    context_folder_path: Optional[str] = None,
) -> str:
    """Asynchronously resolve folder key from provided parameters or instance context.

    Args:
        folder_key: Optional folder key to use directly
        folder_path: Optional folder path to resolve to a key
        folders_service: FolderService instance to resolve folder paths
        context_folder_key: Optional instance-level folder key fallback
        context_folder_path: Optional instance-level folder path fallback

    Returns:
        The resolved folder key

    Raises:
        ValueError: If folder key cannot be resolved
    """
    if folder_key is not None:
        return folder_key

    if folder_path is not None:
        return await folders_service.retrieve_folder_key_async(folder_path=folder_path)

    if context_folder_key is not None:
        return context_folder_key

    if context_folder_path is not None:
        return await folders_service.retrieve_folder_key_async(
            folder_path=context_folder_path
        )

    raise ValueError("Failed to resolve folder key")
