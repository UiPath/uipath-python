import json
import uuid
from typing import Any, Dict, List, Optional, overload

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder
from ..models import Attachment
from ..models.job import Job
from ..tracing._traced import traced
from ._base_service import BaseService


class JobsService(FolderContext, BaseService):
    """Service for managing API payloads and job inbox interactions.

    A job represents a single execution of an automation - it is created when you start
      a process and contains information about that specific run, including its status,
      start time, and any input/output data.
    """

    def __init__(self, config: Config, execution_context: ExecutionContext) -> None:
        super().__init__(config=config, execution_context=execution_context)

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
            content=spec.content,
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

            from uipath import UiPath

            sdk = UiPath()


            async def main():  # noqa: D103
                payload = await sdk.jobs.resume_async(job_id="38073051", payload="The response")
                print(payload)


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
            content=spec.content,
        )

    @property
    def custom_headers(self) -> Dict[str, str]:
        return self.folder_headers

    def retrieve(
        self,
        job_key: str,
    ) -> Job:
        spec = self._retrieve_spec(job_key=job_key)
        response = self.request(
            spec.method,
            url=spec.endpoint,
        )

        return Job.model_validate(response.json())

    async def retrieve_async(
        self,
        job_key: str,
    ) -> Job:
        spec = self._retrieve_spec(job_key=job_key)
        response = await self.request_async(
            spec.method,
            url=spec.endpoint,
        )

        return Job.model_validate(response.json())

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

    def _extract_first_inbox_id(self, response: Any) -> str:
        if len(response["value"]) > 0:
            # FIXME: is this correct?
            return response["value"][0]["ItemKey"]
        else:
            raise Exception("No inbox found")

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
            content=json.dumps({"payload": payload}),
            headers={
                **header_folder(folder_key, folder_path),
            },
        )

    def _retrieve_spec(
        self,
        *,
        job_key: str,
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"/orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})"
            ),
        )

    @traced(name="jobs_list_attachments", run_type="uipath")
    def list_attachments(
        self,
        *,
        job_key: uuid.UUID,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> List[Attachment]:
        """List attachments associated with a specific job.

        This method retrieves all attachments linked to a job by its key.

        Args:
            job_key (uuid.UUID): The key of the job to retrieve attachments for.
            folder_key (Optional[str]): The key of the folder. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Override the default one set in the SDK config.

        Returns:
            List[Attachment]: A list of attachment objects associated with the job.

        Raises:
            Exception: If the retrieval fails.

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            attachments = client.jobs.list_attachments(
                job_key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
            )
            for attachment in attachments:
                print(f"Attachment: {attachment.Name}, Key: {attachment.Key}")
            ```
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

        return [Attachment.model_validate(item) for item in response]

    @traced(name="jobs_list_attachments", run_type="uipath")
    async def list_attachments_async(
        self,
        *,
        job_key: uuid.UUID,
        folder_key: Optional[str] = None,
        folder_path: Optional[str] = None,
    ) -> List[Attachment]:
        """List attachments associated with a specific job asynchronously.

        This method asynchronously retrieves all attachments linked to a job by its key.

        Args:
            job_key (uuid.UUID): The key of the job to retrieve attachments for.
            folder_key (Optional[str]): The key of the folder. Override the default one set in the SDK config.
            folder_path (Optional[str]): The path of the folder. Override the default one set in the SDK config.

        Returns:
            List[Attachment]: A list of attachment objects associated with the job.

        Raises:
            Exception: If the retrieval fails.

        Examples:
            ```python
            import asyncio
            from uipath import UiPath

            client = UiPath()

            async def main():
                attachments = await client.jobs.list_attachments_async(
                    job_key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000")
                )
                for attachment in attachments:
                    print(f"Attachment: {attachment.Name}, Key: {attachment.Key}")
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

        return [Attachment.model_validate(item) for item in response]

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

        Examples:
            ```python
            from uipath import UiPath

            client = UiPath()

            client.jobs.link_attachment(
                attachment_key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000"),
                job_key=uuid.UUID("123e4567-e89b-12d3-a456-426614174001"),
                category="Result"
            )
            print("Attachment linked to job successfully")
            ```
        """
        spec = self._link_job_attachment_spec(
            attachment_key=attachment_key,
            job_key=job_key,
            category=category,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        return self.request(
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

        Examples:
            ```python
            import asyncio
            from uipath import UiPath

            client = UiPath()

            async def main():
                await client.jobs.link_attachment_async(
                    attachment_key=uuid.UUID("123e4567-e89b-12d3-a456-426614174000"),
                    job_key=uuid.UUID("123e4567-e89b-12d3-a456-426614174001"),
                    category="Result"
                )
                print("Attachment linked to job successfully")
            ```
        """
        spec = self._link_job_attachment_spec(
            attachment_key=attachment_key,
            job_key=job_key,
            category=category,
            folder_key=folder_key,
            folder_path=folder_path,
        )

        return await self.request_async(
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
