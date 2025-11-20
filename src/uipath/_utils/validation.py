"""Validation utilities for SDK services."""


def validate_pagination_params(
    skip: int,
    top: int,
    max_skip: int = 10000,
    max_top: int = 1000,
) -> None:
    """Validate pagination parameters for OData queries.

    This validator is used across multiple services (BucketsService, JobsService, etc.)
    to ensure consistent pagination behavior.

    Args:
        skip: Number of items to skip (must be >= 0 and <= max_skip)
        top: Maximum items per page (must be >= 1 and <= max_top)
        max_skip: Maximum allowed skip value (default: 10000)
        max_top: Maximum allowed top value (default: 1000)

    Raises:
        ValueError: If parameters are invalid

    Examples:
        >>> validate_pagination_params(skip=0, top=100)
        >>> validate_pagination_params(skip=5000, top=500)
        >>> validate_pagination_params(skip=-1, top=100)  # Raises ValueError
        >>> validate_pagination_params(skip=0, top=2000)  # Raises ValueError
    """
    if skip < 0:
        raise ValueError("skip must be >= 0")
    if skip > max_skip:
        raise ValueError(
            f"skip must be <= {max_skip} (requested: {skip}). "
            f"Use filters to narrow results or manual pagination."
        )
    if top < 1:
        raise ValueError("top must be >= 1")
    if top > max_top:
        raise ValueError(
            f"top must be <= {max_top} (requested: {top}). "
            f"Use pagination with skip and top parameters."
        )
