import json
from typing import Any, Dict, Optional, overload

from .._config import Config
from .._execution_context import ExecutionContext
from .._folder_context import FolderContext
from .._utils import Endpoint, RequestSpec, header_folder
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
                f"orchestrator_/odata/Jobs/UiPath.Server.Configuration.OData.GetByKey(identifier={job_key})"
            ),
        )
