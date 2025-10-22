from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from ..tracing._traced import traced

if TYPE_CHECKING:
    from .._services.buckets_service import BucketsService


class BucketFile(BaseModel):
    """Represents a file within a bucket."""

    model_config = ConfigDict(
        populate_by_name=True,
        validate_by_alias=True,
    )

    full_path: str = Field(alias="fullPath", description="Full path within bucket")
    content_type: Optional[str] = Field(
        default=None, alias="contentType", description="MIME type"
    )
    size: int = Field(alias="size", description="File size in bytes")
    last_modified: str = Field(
        alias="lastModified", description="Last modification timestamp (ISO format)"
    )

    @property
    def path(self) -> str:
        """Alias for full_path for consistency."""
        return self.full_path

    @property
    def name(self) -> str:
        """Extract filename from full path."""
        return (
            self.full_path.split("/")[-1] if "/" in self.full_path else self.full_path
        )


class Bucket(BaseModel):
    """Bucket resource with file operations.

    This class represents a bucket and provides methods to manage files within it.
    Do not instantiate directly - use BucketsService.retrieve() or BucketsService.list().
    """

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        use_enum_values=True,
        arbitrary_types_allowed=True,
        extra="allow",
    )
    name: str = Field(alias="Name")
    description: Optional[str] = Field(default=None, alias="Description")
    identifier: str = Field(alias="Identifier")
    storage_provider: Optional[str] = Field(default=None, alias="StorageProvider")
    storage_parameters: Optional[str] = Field(default=None, alias="StorageParameters")
    storage_container: Optional[str] = Field(default=None, alias="StorageContainer")
    options: Optional[str] = Field(default=None, alias="Options")
    credential_store_id: Optional[str] = Field(default=None, alias="CredentialStoreId")
    external_name: Optional[str] = Field(default=None, alias="ExternalName")
    password: Optional[str] = Field(default=None, alias="Password")
    folders_count: Optional[int] = Field(default=None, alias="FoldersCount")
    encrypted: Optional[bool] = Field(default=None, alias="Encrypted")
    id: Optional[int] = Field(default=None, alias="Id")
    tags: Optional[List[str]] = Field(default=None, alias="Tags")

    _service: Optional["BucketsService"] = None

    @traced(name="bucket_list_files", run_type="uipath")
    def list(
        self,
        prefix: str = "",
        max_results: int = 500,
        continuation_token: Optional[str] = None,
    ) -> List[BucketFile]:
        """List files in this bucket.

        Args:
            prefix: Path prefix to filter files
            max_results: Maximum number of files to return (default 500, max 1000)
            continuation_token: Token for pagination

        Returns:
            List[BucketFile]: List of files in the bucket

        Examples:
            >>> bucket = sdk.buckets.retrieve(name="my-storage")
            >>> files = bucket.list(prefix="data/")
            >>> for file in files:
            ...     print(f"{file.path} - {file.size} bytes")
        """
        if not self._service:
            raise RuntimeError(
                "Bucket resource not properly initialized. Use BucketsService.retrieve() or list()."
            )

        # Use REST API endpoint that we already tested
        endpoint = f"/orchestrator_/api/Buckets/{self.id}/ListFiles"
        params = {
            "prefix": prefix,
            "takeHint": min(max_results, 1000),
        }
        if continuation_token:
            params["continuationToken"] = continuation_token

        response = self._service.request(
            "GET",
            url=endpoint,
            params=params,
            headers={**self._service.folder_headers},
        ).json()

        files = [BucketFile.model_validate(item) for item in response.get("items", [])]
        return files

    def upload(
        self,
        source_path: str,
        dest_path: str,
        *,
        content_type: Optional[str] = None,
    ) -> None:
        """Upload a file to this bucket.

        Args:
            source_path: Local file path to upload
            dest_path: Destination path in bucket
            content_type: MIME type (auto-detected if not provided)

        Examples:
            >>> bucket = sdk.buckets.retrieve(name="my-storage")
            >>> bucket.upload("local.txt", "remote/data.txt")
        """
        if not self._service:
            raise RuntimeError(
                "Bucket resource not properly initialized. Use BucketsService.retrieve() or list()."
            )

        # Delegate to service upload method
        self._service.upload(
            name=self.name,
            blob_file_path=dest_path,
            source_path=source_path,
            content_type=content_type,
        )

    def download(
        self,
        source_path: str,
        dest_path: str,
    ) -> None:
        """Download a file from this bucket.

        Args:
            source_path: File path in bucket
            dest_path: Local destination path

        Examples:
            >>> bucket = sdk.buckets.retrieve(name="my-storage")
            >>> bucket.download("remote/data.txt", "local.txt")
        """
        if not self._service:
            raise RuntimeError(
                "Bucket resource not properly initialized. Use BucketsService.retrieve() or list()."
            )

        # Delegate to service download method
        self._service.download(
            name=self.name,
            blob_file_path=source_path,
            destination_path=dest_path,
        )

    @traced(name="bucket_delete", run_type="uipath")
    def delete(self, force: bool = False) -> None:
        """Delete this bucket.

        Args:
            force: If True, delete even if bucket contains files (not currently used)

        Examples:
            >>> bucket = sdk.buckets.retrieve(name="my-storage")
            >>> bucket.delete()
        """
        if not self._service:
            raise RuntimeError(
                "Bucket resource not properly initialized. Use BucketsService.retrieve() or list()."
            )

        # Use DELETE endpoint
        endpoint = f"/orchestrator_/odata/Buckets({self.id})"
        self._service.request(
            "DELETE",
            url=endpoint,
            headers={**self._service.folder_headers},
        )
