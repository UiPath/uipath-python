"""Metadata configuration for Buckets service CLI.

This module defines the ServiceMetadata for the buckets service, which is used
by ServiceCLIGenerator to auto-generate standard CRUD commands.

The buckets service was the first service migrated to the Service CLI Generator
architecture and serves as the reference implementation for future migrations.
"""

from uipath._cli._utils._service_metadata import (
    CreateParameter,
    DeleteCommandConfig,
    ExistsCommandConfig,
    ServiceMetadata,
)
from uipath._cli._utils._service_protocol import validate_service_protocol

__all__ = ["BUCKETS_METADATA"]


BUCKETS_METADATA = ServiceMetadata(
    service_name="buckets",
    service_attr="buckets",
    resource_type="Bucket",
    resource_plural="Buckets",
    create_params={
        "description": CreateParameter(
            type="str",
            required=False,
            help="Bucket description",
            default=None,
        ),
    },
    delete_cmd=DeleteCommandConfig(
        confirmation_required=True,
        dry_run_supported=True,
        confirmation_prompt=None,
    ),
    exists_cmd=ExistsCommandConfig(
        identifier_arg_name="name",
        return_format="dict",
    ),
)

BUCKETS_METADATA.validate_types()

try:
    from uipath.sdk import SDK  # type: ignore[import-not-found]

    sdk = SDK()
    validate_service_protocol(sdk.client.buckets, "buckets")
except Exception:
    pass
