import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, cast, overload

from ..._utils import Endpoint, RequestSpec, header_folder, resource_override
from ..._utils.constants import TEMP_ATTACHMENTS_FOLDER
from ..._utils.validation import validate_pagination_params
from ...tracing import traced
from ..common import BaseService, FolderContext, UiPathApiConfig, UiPathExecutionContext
from ..common.paging import PagedResult
from ..errors import EnrichedException
from ._attachments_service import AttachmentsService
from .job import Job


class JobsService(FolderContext, BaseService):
    """Service for managing API payloads and job inbox interactions.

    A job represents a single execution of an automation - it is created when you start
      a process and contains information about that specific run, including its status,
      start time, and any input/output data.
    """

    # Pagination limits
    MAX_PAGE_SIZE = 1000  # Maximum items per page
    MAX_SKIP_OFFSET = 10000  # Maximum skip offset

    def __init__(
        self, config: UiPathApiConfig, execution_context: UiPathExecutionContext
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)
        self._attachments_service = AttachmentsService(config, execution_context)
        # Define the temp directory path for local attachments
        self._temp_dir = os.path.join(tempfile.gettempdir(), TEMP_ATTACHMENTS_FOLDER)
        os.makedirs(self._temp_dir, exist_ok=True)

    @overload
    def resume(self, *, inbox_id: str, payload: Any) -> None: ...

    @overload
    def resume(self, *, job_id: str, payload: Any) -> None: ...

    @traced(name="jobs_resume", run_type="uipath")
    def resume(
        self,
        *,
        inbox_id: Optional[str] = None,
        job_id: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
        payload: Any,
    ) -> None:
        """Sends a payload to resume a paused job waiting for input, identified by its inbox ID.

        Args:
            inbox_id (Optional[str]): The inbox ID of the job.
            job_id (Optional[str]): The job ID of the job.
            folder_key (Optional[str]): The key of the folder to execute the process in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to execute the process in. Override the default one set in the SDK config.
            payload (Any): The payload to deliver.
        """
        if job_id is None and inbox_id is None:
            raise ValueError("Either job_id or inbox_id must be provided")

        # for type checking
        job_id = str(job_id)
        inbox_id = (
            inbox_id
            if inbox_id
            else self._retrieve_inbox_id(
                job_id=job_id,
                folder_key=folder_key,
                folder_path=folder_path,
            )
        )
        spec = self._resume_spec(
            inbox_id=inbox_id,
            payload=payload,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        self.request(
            spec.method,
            url=spec.endpoint,
            headers=spec.headers,
            json=spec.json,
        )

    async def resume_async(
        self,
        *,
        inbox_id: Optional[str] = None,
        job_id: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
        payload: Any,
    ) -> None:
        """Asynchronously sends a payload to resume a paused job waiting for input, identified by its inbox ID.

        Args:
            inbox_id (Optional[str]): The inbox ID of the job. If not provided, the execution context will be used to retrieve the inbox ID.
            job_id (Optional[str]): The job ID of the job.
            folder_key (Optional[str]): The key of the folder to execute the process in. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder to execute the process in. Override the default one set in the SDK config.
            payload (Any): The payload to deliver.

        Examples:
            ```python
            import asyncio

            from uipath.platform import UiPath

            sdk = UiPath()


            async def main():  # noqa: D103
                payload = await sdk.jobs.resume_async(job_id="38073051", payload="The response")

            asyncio.run(main())
            ```
        """
        if job_id is None and inbox_id is None:
            raise ValueError("Either job_id or inbox_id must be provided")

        # for type checking
        job_id = str(job_id)
        inbox_id = (
            inbox_id
            if inbox_id
            else self._retrieve_inbox_id(
                job_id=job_id,
                folder_key=folder_key,
                folder_path=folder_path,
            )
        )

        spec = self._resume_spec(
            inbox_id=inbox_id,
            payload=payload,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        await self.request_async(
            spec.method,
            url=spec.endpoint,
            headers=spec.headers,
            json=spec.json,
        )

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers

    @traced(name="jobs_list", run_type="uipath")
    def list(
        self,
        *,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        skip: int = 0,
        top: int = 100,
    ) -> PagedResult[Job]:
        """List jobs using OData API with offset-based pagination.

        Returns a single page of results with pagination metadata.

        Args:
            folder_path: Folder path to filter jobs
            folder_key: Folder key (mutually exclusive with folder_path)
            filter: OData $filter expression (e.g., "State eq 'Successful'")
            orderby: OData $orderby expression (e.g., "CreationTime desc")
            skip: Number of items to skip (default 0, max 10000)
            top: Maximum items per page (default 100, max 1000)

        Returns:
            PagedResult[Job]: Page of jobs with pagination metadata

        Raises:
            ValueError: If skip or top parameters are invalid

        Examples:
            >>> result = sdk.jobs.list(top=100)
            >>> for job in result.items:
            ...     print(job.key, job.state)
            >>> print(f"Has more: {result.has_more}")
        """
        validate_pagination_params(
            skip=skip,
            top=top,
            max_skip=self.MAX_SKIP_OFFSET,
            max_top=self.MAX_PAGE_SIZE,
        )

        spec = self._list_spec(
            folder_path=folder_path,
            folder_key=folder_key,
            filter=filter,
            orderby=orderby,
            skip=skip,
            top=top,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        ).json()

        items = response.get("value", [])
        jobs = [Job.model_validate(item) for item in items]

        return PagedResult(
            items=jobs,
            has_more=len(items) == top,
            skip=skip,
            top=top,
        )

    @traced(name="jobs_list", run_type="uipath")
    async def list_async(
        self,
        *,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        filter: Optional[str] = None,
        orderby: Optional[str] = None,
        skip: int = 0,
        top: int = 100,
    ) -> PagedResult[Job]:
        """Async version of list() with offset-based pagination."""
        validate_pagination_params(
            skip=skip,
            top=top,
            max_skip=self.MAX_SKIP_OFFSET,
            max_top=self.MAX_PAGE_SIZE,
        )

        spec = self._list_spec(
            folder_path=folder_path,
            folder_key=folder_key,
            filter=filter,
            orderby=orderby,
            skip=skip,
            top=top,
        )
        response = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
        ).json()

        items = response.get("value", [])
        jobs = [Job.model_validate(item) for item in items]

        return PagedResult(
            items=jobs,
            has_more=len(items) == top,
            skip=skip,
            top=top,
        )

    @traced(name="jobs_stop", run_type="uipath")
    def stop(
        self,
        *,
        job_keys: List[str],
        strategy: str = "SoftStop",
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> None:
        """Stop one or more jobs with specified strategy.

        This method uses bulk resolution to efficiently stop multiple jobs,
        preventing N+1 query issues. Requests are automatically chunked for
        large job lists to avoid URL length constraints.

        Args:
            job_keys: List of job UUID keys to stop
            strategy: Stop strategy - "SoftStop" (graceful) or "Kill" (force)
            folder_path: Folder path
            folder_key: Folder key

        Raises:
            ValueError: If any job key is not a valid UUID format
            LookupError: If any job keys are not found

        Examples:
            >>> sdk.jobs.stop(job_keys=["ee9327fd-237d-419e-86ef-9946b34461e3"])
            >>> sdk.jobs.stop(job_keys=["key1", "key2"], strategy="Kill")

        Note:
            Large batches are automatically chunked (50 keys per request) to
            avoid URL length limits. The method supports stopping hundreds of
            jobs efficiently.
        """
        job_ids = self._resolve_job_identifiers(
            job_keys=job_keys,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        spec = self._stop_spec(
            job_ids=job_ids,
            strategy=strategy,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        self.request(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        )

    @traced(name="jobs_stop", run_type="uipath")
    async def stop_async(
        self,
        *,
        job_keys: List[str],
        strategy: str = "SoftStop",
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> None:
        """Async version of stop()."""
        job_ids = await self._resolve_job_identifiers_async(
            job_keys=job_keys,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        spec = self._stop_spec(
            job_ids=job_ids,
            strategy=strategy,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        await self.request_async(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        )

    @traced(name="jobs_restart", run_type="uipath")
    def restart(
        self,
        *,
        job_key: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> Job:
        """Restart a completed or failed job.

        Args:
            job_key: Job UUID key to restart
            folder_path: Folder path
            folder_key: Folder key

        Returns:
            Job: The restarted job

        Examples:
            >>> restarted_job = sdk.jobs.restart(job_key="ee9327fd-237d-419e-86ef-9946b34461e3")
            >>> print(restarted_job.state)
        """
        job_ids = self._resolve_job_identifiers(
            job_keys=[job_key],
            folder_key=folder_key,
            folder_path=folder_path,
        )

        spec = self._restart_spec(
            job_id=job_ids[0],
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        )

        return Job.model_validate(response.json())

    @traced(name="jobs_restart", run_type="uipath")
    async def restart_async(
        self,
        *,
        job_key: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> Job:
        """Async version of restart()."""
        job_ids = await self._resolve_job_identifiers_async(
            job_keys=[job_key],
            folder_key=folder_key,
            folder_path=folder_path,
        )

        spec = self._restart_spec(
            job_id=job_ids[0],
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            json=spec.json,
            headers=spec.headers,
        )

        return Job.model_validate(response.json())

    @traced(name="jobs_exists", run_type="uipath")
    def exists(
        self,
        job_key: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> bool:
        """Check if job exists.

        Args:
            job_key: Job UUID key
            folder_key: Folder key
            folder_path: Folder path

        Returns:
            bool: True if job exists, False otherwise

        Examples:
            >>> if sdk.jobs.exists(job_key="ee9327fd-237d-419e-86ef-9946b34461e3"):
            ...     print("Job found")
        """
        try:
            self.retrieve(
                job_key=job_key, folder_key=folder_key, folder_path=folder_path
            )
            return True
        except LookupError:
            return False

    @traced(name="jobs_exists", run_type="uipath")
    async def exists_async(
        self,
        job_key: str,
        *,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> bool:
        """Async version of exists()."""
        try:
            await self.retrieve_async(
                job_key=job_key, folder_key=folder_key, folder_path=folder_path
            )
            return True
        except LookupError:
            return False

    @traced(name="jobs_retrieve", run_type="uipath")
    @resource_override(resource_type="process", resource_identifier="process_name")
    def retrieve(
        self,
        job_key: str,
        *,
        folder_key: str | None = None,
        folder_path: str | None = None,
        process_name: str | None = None,
    ) -> Job:
        """Retrieve a job identified by its key.

        Args:
            job_key (str): The job unique identifier.
            folder_key (Optional[str]): The key of the folder in which the job was executed.
            folder_path (Optional[str]): The path of the folder in which the job was executed.
            process_name: process name hint for resource override

        Returns:
            Job: The retrieved job.

        Raises:
            LookupError: If the job with the specified key is not found.

        Examples:
            ```python
            from uipath.platform import UiPath

            sdk = UiPath()
            job = sdk.jobs.retrieve(job_key="ee9327fd-237d-419e-86ef-9946b34461e3", folder_path="Shared")
            ```
        """
        spec = self._retrieve_spec(
            job_key=job_key, folder_key=folder_key, folder_path=folder_path
        )
        try:
            response = self.request(
                spec.method,
                url=spec.endpoint,
                headers=spec.headers,
            )
            return Job.model_validate(response.json())
        except EnrichedException as e:
            if e.status_code == 404:
                raise LookupError(f"Job with key '{job_key}' not found") from e
            raise

    @traced(name="jobs_retrieve_async", run_type="uipath")
    @resource_override(resource_type="process", resource_identifier="process_name")
    async def retrieve_async(
        self,
        job_key: str,
        *,
        folder_key: str | None = None,
        folder_path: str | None = None,
        process_name: str | None = None,
    ) -> Job:
        """Asynchronously retrieve a job identified by its key.

        Args:
            job_key (str): The job unique identifier.
            folder_key (Optional[str]): The key of the folder in which the job was executed.
            folder_path (Optional[str]): The path of the folder in which the job was executed.
            process_name: process name hint for resource override

        Returns:
            Job: The retrieved job.

        Raises:
            LookupError: If the job with the specified key is not found.

        Examples:
            ```python
            import asyncio

            from uipath.platform import UiPath

            sdk = UiPath()


            async def main():  # noqa: D103
                job = await sdk.jobs.retrieve_async(job_key="ee9327fd-237d-419e-86ef-9946b34461e3", folder_path="Shared")

            asyncio.run(main())
            ```
        """
        spec = self._retrieve_spec(
            job_key=job_key, folder_key=folder_key, folder_path=folder_path
        )
        try:
            response = await self.request_async(
                spec.method,
                url=spec.endpoint,
                headers=spec.headers,
            )
            return Job.model_validate(response.json())
        except EnrichedException as e:
            if e.status_code == 404:
                raise LookupError(f"Job with key '{job_key}' not found") from e
            raise

    def _retrieve_inbox_id(
        self,
        *,
        job_id: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> str:
        spec = self._retrieve_inbox_id_spec(
            job_id=job_id,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )

        response = response.json()
        return self._extract_first_inbox_id(response)

    async def _retrieve_inbox_id_async(
        self,
        *,
        job_id: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> str:
        spec = self._retrieve_inbox_id_spec(
            job_id=job_id,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        )

        response = response.json()
        return self._extract_first_inbox_id(response)

    def retrieve_api_payload(self, inbox_id: str) -> Any:
        """Fetch payload data for API triggers.

        Args:
            inbox_id: The Id of the inbox to fetch the payload for.

        Returns:
            The value field from the API response payload.
        """
        spec = self._retrieve_api_payload_spec(inbox_id=inbox_id)

        response = self.request(
            spec.method,
            url=spec.endpoint,
            headers=spec.headers,
        )

        data = response.json()
        return data.get("payload")

    async def retrieve_api_payload_async(self, inbox_id: str) -> Any:
        """Asynchronously fetch payload data for API triggers.

        Args:
            inbox_id: The Id of the inbox to fetch the payload for.

        Returns:
            The value field from the API response payload.
        """
        spec = self._retrieve_api_payload_spec(inbox_id=inbox_id)

        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
            headers=spec.headers,
        )

        data = response.json()
        return data.get("payload")

    def _retrieve_api_payload_spec(
        self,
        *,
        inbox_id: str,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/orchestrator_/api/JobTriggers/GetPayload/{inbox_id}"),
            headers={
                **self.folder_headers,
            },
        )

    def _extract_first_inbox_id(self, response: Any) -> str:
        if len(response["value"]) > 0:
            return response["value"][0]["ItemKey"]
        else:
            raise LookupError("No inbox found")

    def _retrieve_inbox_id_spec(
        self,
        *,
        job_id: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/JobTriggers"),
            params={
                "$filter": f"JobId eq {job_id}",
                "$top": 1,
                "$select": "ItemKey",
            },
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def extract_output(self, job: Job) -> Optional[str]:
        """Get the actual output data, downloading from attachment if necessary.

        Args:
            job: The job instance to fetch output data from.

        Returns:
            Parsed output arguments as dictionary, or None if no output
        """
        if job.output_file:
            # Large output stored as attachment
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / f"output_{job.output_file}"
                self._attachments_service.download(
                    key=uuid.UUID(job.output_file), destination_path=temp_path
                )
                with open(temp_path, "r", encoding="utf-8") as f:
                    return f.read()
        elif job.output_arguments:
            # Small output stored inline
            return job.output_arguments
        else:
            return None

    async def extract_output_async(self, job: Job) -> Optional[str]:
        """Asynchronously fetch the actual output data, downloading from attachment if necessary.

        Args:
            job: The job instance to fetch output data from.

        Returns:
            Parsed output arguments as dictionary, or None if no output
        """
        if job.output_file:
            # Large output stored as attachment
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir) / f"output_{job.output_file}"
                await self._attachments_service.download_async(
                    key=uuid.UUID(job.output_file), destination_path=temp_path
                )
                with open(temp_path, "r", encoding="utf-8") as f:
                    return f.read()
        elif job.output_arguments:
            # Small output stored inline
            return job.output_arguments
        else:
            return None

    def _resume_spec(
        self,
        *,
        inbox_id: str,
        payload: Any = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                f"/orchestrator_/api/JobTriggers/DeliverPayload/{inbox_id}"
            ),
            json={"payload": payload},
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _retrieve_spec(
        self,
        *,
        job_key: str,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})"
            ),
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    @traced(name="jobs_list_attachments", run_type="uipath")
    def list_attachments(
        self,
        *,
        job_key: uuid.UUID,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> List[str]:
        """List attachments associated with a specific job.

        This method retrieves all attachments linked to a job by its key.

        Args:
            job_key (uuid.UUID): The key of the job to retrieve attachments for.
            folder_key (Optional[str]): The key of the folder. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Override the default one set in the SDK config.

        Returns:
            List[str]: A list of attachment IDs associated with the job.

        Raises:
            Exception: If the retrieval fails.
        """
        spec = self._list_job_attachments_spec(
            job_key=job_key,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        ).json()

        return [item.get("attachmentId") for item in response]

    @traced(name="jobs_list_attachments", run_type="uipath")
    async def list_attachments_async(
        self,
        *,
        job_key: uuid.UUID,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> List[str]:
        """List attachments associated with a specific job asynchronously.

        This method asynchronously retrieves all attachments linked to a job by its key.

        Args:
            job_key (uuid.UUID): The key of the job to retrieve attachments for.
            folder_key (Optional[str]): The key of the folder. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Override the default one set in the SDK config.

        Returns:
            List[str]: A list of attachment IDs associated with the job.

        Raises:
            Exception: If the retrieval fails.

        Examples:
            ```python
            import asyncio
            from uipath.platform import UiPath

            client = UiPath()

            async def main():
                attachments = await client.jobs.list_attachments_async(
                    job_key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
                )
                for attachment_id in attachments:
                    print(f"Attachment ID: {attachment_id}")
            ```
        """
        spec = self._list_job_attachments_spec(
            job_key=job_key,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        response = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
        ).json()

        return [item.get("attachmentId") for item in response]

    @traced(name="jobs_link_attachment", run_type="uipath")
    def link_attachment(
        self,
        *,
        attachment_key: uuid.UUID,
        job_key: uuid.UUID,
        category: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ):
        """Link an attachment to a job.

        This method links an existing attachment to a specific job.

        Args:
            attachment_key (uuid.UUID): The key of the attachment to link.
            job_key (uuid.UUID): The key of the job to link the attachment to.
            category (Optional[str]): Optional category for the attachment in the context of this job.
            folder_key (Optional[str]): The key of the folder. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Override the default one set in the SDK config.

        Raises:
            Exception: If the link operation fails.
        """
        spec = self._link_job_attachment_spec(
            attachment_key=attachment_key,
            job_key=job_key,
            category=category,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        self.request(
            spec.method,
            url=spec.endpoint,
            headers=spec.headers,
            json=spec.json,
        )

    @traced(name="jobs_link_attachment", run_type="uipath")
    async def link_attachment_async(
        self,
        *,
        attachment_key: uuid.UUID,
        job_key: uuid.UUID,
        category: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ):
        """Link an attachment to a job asynchronously.

        This method asynchronously links an existing attachment to a specific job.

        Args:
            attachment_key (uuid.UUID): The key of the attachment to link.
            job_key (uuid.UUID): The key of the job to link the attachment to.
            category (Optional[str]): Optional category for the attachment in the context of this job.
            folder_key (Optional[str]): The key of the folder. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Override the default one set in the SDK config.

        Raises:
            Exception: If the link operation fails.
        """
        spec = self._link_job_attachment_spec(
            attachment_key=attachment_key,
            job_key=job_key,
            category=category,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        await self.request_async(
            spec.method,
            url=spec.endpoint,
            headers=spec.headers,
            json=spec.json,
        )

    def _list_job_attachments_spec(
        self,
        job_key: uuid.UUID,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/api/JobAttachments/GetByJobKey"),
            params={
                "jobKey": job_key,
            },
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _link_job_attachment_spec(
        self,
        attachment_key: uuid.UUID,
        job_key: uuid.UUID,
        category: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint("/orchestrator_/api/JobAttachments/Post"),
            json={
                "attachmentId": str(attachment_key),
                "jobKey": str(job_key),
                "category": category,
            },
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    @traced(name="jobs_create_attachment", run_type="uipath")
    def create_attachment(
        self,
        *,
        name: str,
        content: Optional[Union[str, bytes]] = None,
        source_path: Optional[Union[str, Path]] = None,
        job_key: Optional[Union[str, uuid.UUID]] = None,
        category: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> uuid.UUID:
        """Create and upload an attachment, optionally linking it to a job.

        This method handles creating an attachment from a file or memory data.
        If a job key is provided or available in the execution context, the attachment
        will be created in UiPath and linked to the job. If no job is available,
        the file will be saved to a temporary storage folder.

        Note:
            The local storage functionality (when no job is available) is intended for
            local development and debugging purposes only.

        Args:
            name (str): The name of the attachment file.
            content (Optional[Union[str, bytes]]): The content to upload (string or bytes).
            source_path (Optional[Union[str, Path]]): The local path of the file to upload.
            job_key (Optional[Union[str, uuid.UUID]]): The key of the job to link the attachment to.
            category (Optional[str]): Optional category for the attachment in the context of the job.
            folder_key (Optional[str]): The key of the folder. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Override the default one set in the SDK config.

        Returns:
            uuid.UUID: The unique identifier for the created attachment, regardless of whether it was
                uploaded to UiPath or stored locally.

        Raises:
            ValueError: If neither content nor source_path is provided, or if both are provided.
            Exception: If the upload fails.

        Examples:
            ```python
            from uipath.platform import UiPath

            client = UiPath()

            # Create attachment from file and link to job
            attachment_id = client.jobs.create_attachment(
                name="document.pdf",
                source_path="path/to/local/document.pdf",
                job_key="38073051"
            )
            print(f"Created and linked attachment: {attachment_id}")

            # Create attachment from memory content (no job available - saves to temp storage)
            attachment_id = client.jobs.create_attachment(
                name="report.txt",
                content="This is a text report"
            )
            print(f"Created attachment: {attachment_id}")
            ```
        """
        # Validate input parameters
        if not (content or source_path):
            raise ValueError("Content or source_path is required")
        if content and source_path:
            raise ValueError("Content and source_path are mutually exclusive")

        # Get job key from context if not explicitly provided
        context_job_key = None
        if job_key is None:
            try:
                context_job_key = self._execution_context.instance_key
            except ValueError:
                # Instance key is not set in environment
                context_job_key = None

        # Check if a job is available
        if job_key is not None or context_job_key is not None:
            # Job is available - create attachment in UiPath and link to job
            actual_job_key = job_key if job_key is not None else context_job_key

            # Create the attachment using the attachments service
            if content is not None:
                attachment_key = self._attachments_service.upload(
                    name=name,
                    content=content,
                    folder_key=folder_key,
                    folder_path=folder_path,
                )
            else:
                # source_path must be provided due to validation check above
                attachment_key = self._attachments_service.upload(
                    name=name,
                    source_path=cast(str, source_path),
                    folder_key=folder_key,
                    folder_path=folder_path,
                )

            # Convert to UUID if string
            if isinstance(actual_job_key, str):
                actual_job_key = uuid.UUID(actual_job_key)

            # Link attachment to job
            self.link_attachment(
                attachment_key=attachment_key,
                job_key=cast(uuid.UUID, actual_job_key),
                category=category,
                folder_key=folder_key,
                folder_path=folder_path,
            )

            return attachment_key
        else:
            # No job available - save to temp folder
            # Generate a UUID to use as identifier
            attachment_id = uuid.uuid4()

            # Create destination file path
            dest_path = os.path.join(self._temp_dir, f"{attachment_id}_{name}")

            # If we have source_path, copy the file
            if source_path is not None:
                source_path_str = (
                    source_path if isinstance(source_path, str) else str(source_path)
                )
                shutil.copy2(source_path_str, dest_path)
            # If we have content, write it to a file
            elif content is not None:
                # Convert string to bytes if needed
                if isinstance(content, str):
                    content = content.encode("utf-8")

                with open(dest_path, "wb") as f:
                    f.write(content)

            # Return only the UUID
            return attachment_id

    @traced(name="jobs_create_attachment", run_type="uipath")
    async def create_attachment_async(
        self,
        *,
        name: str,
        content: Optional[Union[str, bytes]] = None,
        source_path: Optional[Union[str, Path]] = None,
        job_key: Optional[Union[str, uuid.UUID]] = None,
        category: Optional[str] = None,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> uuid.UUID:
        """Create and upload an attachment asynchronously, optionally linking it to a job.

        This method asynchronously handles creating an attachment from a file or memory data.
        If a job key is provided or available in the execution context, the attachment
        will be created in UiPath and linked to the job. If no job is available,
        the file will be saved to a temporary storage folder.

        Note:
            The local storage functionality (when no job is available) is intended for
            local development and debugging purposes only.

        Args:
            name (str): The name of the attachment file.
            content (Optional[Union[str, bytes]]): The content to upload (string or bytes).
            source_path (Optional[Union[str, Path]]): The local path of the file to upload.
            job_key (Optional[Union[str, uuid.UUID]]): The key of the job to link the attachment to.
            category (Optional[str]): Optional category for the attachment in the context of the job.
            folder_key (Optional[str]): The key of the folder. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Override the default one set in the SDK config.

        Returns:
            uuid.UUID: The unique identifier for the created attachment, regardless of whether it was
                uploaded to UiPath or stored locally.

        Raises:
            ValueError: If neither content nor source_path is provided, or if both are provided.
            Exception: If the upload fails.

        Examples:
            ```python
            import asyncio
            from uipath.platform import UiPath

            client = UiPath()

            async def main():
                # Create attachment from file and link to job
                attachment_id = await client.jobs.create_attachment_async(
                    name="document.pdf",
                    source_path="path/to/local/document.pdf",
                    job_key="38073051"
                )
                print(f"Created and linked attachment: {attachment_id}")

                # Create attachment from memory content (no job available - saves to temp storage)
                attachment_id = await client.jobs.create_attachment_async(
                    name="report.txt",
                    content="This is a text report"
                )
                print(f"Created attachment: {attachment_id}")
            ```
        """
        # Validate input parameters
        if not (content or source_path):
            raise ValueError("Content or source_path is required")
        if content and source_path:
            raise ValueError("Content and source_path are mutually exclusive")

        # Get job key from context if not explicitly provided
        context_job_key = None
        if job_key is None:
            try:
                context_job_key = self._execution_context.instance_key
            except ValueError:
                # Instance key is not set in environment
                context_job_key = None

        # Check if a job is available
        if job_key is not None or context_job_key is not None:
            # Job is available - create attachment in UiPath and link to job
            actual_job_key = job_key if job_key is not None else context_job_key

            # Create the attachment using the attachments service
            if content is not None:
                attachment_key = await self._attachments_service.upload_async(
                    name=name,
                    content=content,
                    folder_key=folder_key,
                    folder_path=folder_path,
                )
            else:
                # source_path must be provided due to validation check above
                attachment_key = await self._attachments_service.upload_async(
                    name=name,
                    source_path=cast(str, source_path),
                    folder_key=folder_key,
                    folder_path=folder_path,
                )

            # Convert to UUID if string
            if isinstance(actual_job_key, str):
                actual_job_key = uuid.UUID(actual_job_key)

            # Link attachment to job
            await self.link_attachment_async(
                attachment_key=attachment_key,
                job_key=cast(uuid.UUID, actual_job_key),
                category=category,
                folder_key=folder_key,
                folder_path=folder_path,
            )

            return attachment_key
        else:
            # No job available - save to temp folder
            # Generate a UUID to use as identifier
            attachment_id = uuid.uuid4()

            # Create destination file path
            dest_path = os.path.join(self._temp_dir, f"{attachment_id}_{name}")

            # If we have source_path, copy the file
            if source_path is not None:
                source_path_str = (
                    source_path if isinstance(source_path, str) else str(source_path)
                )
                shutil.copy2(source_path_str, dest_path)
            # If we have content, write it to a file
            elif content is not None:
                # Convert string to bytes if needed
                if isinstance(content, str):
                    content = content.encode("utf-8")

                with open(dest_path, "wb") as f:
                    f.write(content)

            # Return only the UUID
            return attachment_id

    def _list_spec(
        self,
        folder_path: Optional[str],
        folder_key: Optional[str],
        filter: Optional[str],
        orderby: Optional[str],
        skip: int,
        top: int,
    ) -> RequestSpec:
        """Build OData request for listing jobs."""
        params: Dict[str, Any] = {"$skip": skip, "$top": top}
        if filter:
            params["$filter"] = filter
        if orderby:
            params["$orderby"] = orderby

        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/orchestrator_/odata/Jobs"),
            params=params,
            headers={**header_folder(folder_key, folder_path)},
        )

    def _stop_spec(
        self,
        job_ids: List[int],
        strategy: str,
        folder_key: Optional[str],
        folder_path: Optional[str],
    ) -> RequestSpec:
        """Build request for stopping jobs with strategy.

        Pure function - no HTTP calls, no side effects.

        Args:
            job_ids: List of job integer IDs (already resolved)
            strategy: Stop strategy ("SoftStop" or "Kill")
            folder_key: Folder key
            folder_path: Folder path

        Returns:
            RequestSpec: Request specification for StopJobs endpoint
        """
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                "/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.StopJobs"
            ),
            json={
                "jobIds": job_ids,
                "strategy": strategy,
            },
            headers={**header_folder(folder_key, folder_path)},
        )

    def _restart_spec(
        self,
        job_id: int,
        folder_key: Optional[str],
        folder_path: Optional[str],
    ) -> RequestSpec:
        """Build request for restarting a job."""
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(
                "/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.RestartJob"
            ),
            json={"jobId": job_id},
            headers={**header_folder(folder_key, folder_path)},
        )

    def _resolve_job_identifiers(
        self,
        job_keys: List[str],
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> List[int]:
        """Resolve job keys to job IDs in chunked bulk queries.

        This method prevents N+1 query issues by fetching all job IDs using
        OData $filter with 'in' operator. Requests are chunked to avoid URL
        length limits (max 50 keys per request).

        Args:
            job_keys: List of job UUID keys to resolve
            folder_key: Folder key
            folder_path: Folder path

        Returns:
            List[int]: List of job integer IDs in same order as job_keys

        Raises:
            ValueError: If any job key is not a valid UUID
            LookupError: If any job key is not found

        Note:
            Duplicate keys in input are allowed and will return corresponding IDs.
        """
        if not job_keys:
            return []

        for key in job_keys:
            try:
                uuid.UUID(key)
            except ValueError as e:
                raise ValueError(f"Invalid job key format: {key}") from e

        unique_keys = []
        seen = set()
        for key in job_keys:
            if key not in seen:
                unique_keys.append(key)
                seen.add(key)

        CHUNK_SIZE = 50
        all_key_to_id: Dict[str, int] = {}

        for i in range(0, len(unique_keys), CHUNK_SIZE):
            chunk = unique_keys[i : i + CHUNK_SIZE]
            keys_formatted = "','".join(chunk)
            filter_expr = f"Key in ('{keys_formatted}')"

            spec = RequestSpec(
                method="GET",
                endpoint=Endpoint("/orchestrator_/odata/Jobs"),
                params={
                    "$filter": filter_expr,
                    "$select": "Id,Key",
                    "$top": len(chunk),
                },
                headers={**header_folder(folder_key, folder_path)},
            )

            response = self.request(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            ).json()

            items = response.get("value", [])

            # Accumulate mappings from this chunk
            for item in items:
                all_key_to_id[item["Key"]] = item["Id"]

        # Verify all unique keys were found
        if len(all_key_to_id) != len(unique_keys):
            found_keys = set(all_key_to_id.keys())
            missing_keys = set(unique_keys) - found_keys
            raise LookupError(f"Jobs not found for keys: {', '.join(missing_keys)}")

        # Build result preserving original order (including duplicates)
        return [all_key_to_id[key] for key in job_keys]

    async def _resolve_job_identifiers_async(
        self,
        job_keys: List[str],
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> List[int]:
        """Async version of _resolve_job_identifiers()."""
        if not job_keys:
            return []

        for key in job_keys:
            try:
                uuid.UUID(key)
            except ValueError as e:
                raise ValueError(f"Invalid job key format: {key}") from e

        unique_keys = []
        seen = set()
        for key in job_keys:
            if key not in seen:
                unique_keys.append(key)
                seen.add(key)

        CHUNK_SIZE = 50
        all_key_to_id: Dict[str, int] = {}

        for i in range(0, len(unique_keys), CHUNK_SIZE):
            chunk = unique_keys[i : i + CHUNK_SIZE]
            keys_formatted = "','".join(chunk)
            filter_expr = f"Key in ('{keys_formatted}')"

            spec = RequestSpec(
                method="GET",
                endpoint=Endpoint("/orchestrator_/odata/Jobs"),
                params={
                    "$filter": filter_expr,
                    "$select": "Id,Key",
                    "$top": len(chunk),
                },
                headers={**header_folder(folder_key, folder_path)},
            )

            response = (
                await self.request_async(
                    spec.method,
                    url=spec.endpoint,
                    params=spec.params,
                    headers=spec.headers,
                )
            ).json()

            items = response.get("value", [])

            for item in items:
                all_key_to_id[item["Key"]] = item["Id"]

        if len(all_key_to_id) != len(unique_keys):
            found_keys = set(all_key_to_id.keys())
            missing_keys = set(unique_keys) - found_keys
            raise LookupError(f"Jobs not found for keys: {', '.join(missing_keys)}")

        return [all_key_to_id[key] for key in job_keys]
