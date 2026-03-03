"""Protocol definition for CRUD services.

This module defines the CRUDServiceProtocol that services must implement
to be compatible with the CLI command generator.

The protocol uses Python's Protocol (PEP 544) for structural subtyping,
allowing duck-typing without requiring explicit inheritance.

Example:
    >>> from typing import Protocol, runtime_checkable
    >>> from ._service_protocol import CRUDServiceProtocol
    >>>
    >>> # A service that implements the protocol
    >>> class BucketsService:
    ...     def list(self, folder_path=None, folder_key=None):
    ...         return iter([])
    ...
    ...     def retrieve(self, name, folder_path=None, folder_key=None):
    ...         return {"name": name}
    ...
    ...     # ... other CRUD methods
    >>>
    >>> # No explicit inheritance needed - structural typing
    >>> def use_service(service: CRUDServiceProtocol):
    ...     return list(service.list())
"""

from typing import Any, Iterator, Protocol, runtime_checkable


@runtime_checkable
class CRUDServiceProtocol(Protocol):
    """Protocol for services that support standard CRUD operations.

    Services implementing this protocol can use the ServiceCLIGenerator
    to automatically generate CLI commands.

    All methods support folder-scoped operations via folder_path or folder_key
    parameters. This matches the UiPath platform's hierarchical folder structure.

    Required Methods:
        list: List all resources (returns iterator)
        retrieve: Get a single resource by identifier
        create: Create a new resource
        delete: Delete a resource by identifier

    Optional Methods (NOT in protocol, checked separately):
        exists: Check if a resource exists (will be used if present on service)

    Note:
        This is a Protocol, not a base class. Services don't need to inherit
        from it; they just need to implement the required methods with
        compatible signatures.

        The exists() method is NOT part of the protocol to allow optional
        implementation. Use hasattr(service, 'exists') to check for it.
    """

    def list(
        self,
        *,
        folder_path: str | None = None,
        folder_key: str | None = None,
        **kwargs: Any,
    ) -> Iterator[Any]:
        """List all resources in the specified folder.

        Args:
            folder_path: Folder path (e.g., "Shared")
            folder_key: Folder UUID key
            **kwargs: Additional service-specific parameters

        Returns:
            Iterator of resource objects

        Example:
            >>> buckets_service.list(folder_path="Shared")
            <iterator of Bucket objects>
        """
        ...

    def retrieve(
        self,
        name: str,
        *,
        folder_path: str | None = None,
        folder_key: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Retrieve a single resource by identifier.

        Args:
            name: Resource identifier (usually name, but could be key)
            folder_path: Folder path (e.g., "Shared")
            folder_key: Folder UUID key
            **kwargs: Additional service-specific parameters

        Returns:
            Resource object

        Raises:
            LookupError: If resource not found

        Example:
            >>> buckets_service.retrieve("my-bucket", folder_path="Shared")
            Bucket(name="my-bucket", ...)
        """
        ...

    def create(
        self,
        name: str,
        *,
        folder_path: str | None = None,
        folder_key: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Create a new resource.

        Args:
            name: Resource name
            folder_path: Folder path (e.g., "Shared")
            folder_key: Folder UUID key
            **kwargs: Additional service-specific parameters (from metadata)

        Returns:
            Created resource object

        Example:
            >>> buckets_service.create(
            ...     "my-bucket",
            ...     folder_path="Shared",
            ...     description="My bucket"
            ... )
            Bucket(name="my-bucket", description="My bucket", ...)
        """
        ...

    def delete(
        self,
        name: str,
        *,
        folder_path: str | None = None,
        folder_key: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Delete a resource by identifier.

        Args:
            name: Resource identifier to delete
            folder_path: Folder path (e.g., "Shared")
            folder_key: Folder UUID key
            **kwargs: Additional service-specific parameters

        Raises:
            LookupError: If resource not found

        Example:
            >>> buckets_service.delete("my-bucket", folder_path="Shared")
        """
        ...


def has_exists_method(service: Any) -> bool:
    """Check if a service has the optional exists() method.

    This is separate from the Protocol because exists() is optional.
    Not all services need to implement it.

    Args:
        service: Service instance to check

    Returns:
        True if service has a callable exists() method

    Example:
        >>> class ServiceWithExists:
        ...     def exists(self, name, **kwargs):
        ...         return True
        >>>
        >>> service = ServiceWithExists()
        >>> has_exists_method(service)
        True
    """
    return hasattr(service, "exists") and callable(service.exists)


def validate_service_protocol(service: Any, service_name: str) -> None:
    """Validate that a service implements the CRUDServiceProtocol.

    Args:
        service: Service instance to validate
        service_name: Name of the service for error messages

    Raises:
        TypeError: If service doesn't implement required methods

    Example:
        >>> class IncompleteService:
        ...     def list(self):
        ...         pass
        ...     # Missing other methods
        >>>
        >>> validate_service_protocol(IncompleteService(), "incomplete")
        Traceback (most recent call last):
        ...
        TypeError: Service 'incomplete' must implement: retrieve, create, delete
    """
    required_methods = ["list", "retrieve", "create", "delete"]
    missing_methods = []
    for method_name in required_methods:
        if not hasattr(service, method_name) or not callable(
            getattr(service, method_name)
        ):
            missing_methods.append(method_name)

    if missing_methods:
        raise TypeError(
            f"Service '{service_name}' must implement: {', '.join(missing_methods)}"
        )


__all__ = ["CRUDServiceProtocol", "validate_service_protocol", "has_exists_method"]
