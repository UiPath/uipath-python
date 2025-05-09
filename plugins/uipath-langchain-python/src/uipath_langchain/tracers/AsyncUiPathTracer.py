import asyncio
import json
import logging
import queue
import uuid
import warnings
from os import environ as env
from typing import Any, Dict, Optional

import httpx
from langchain_core.tracers.base import AsyncBaseTracer
from langchain_core.tracers.schemas import Run
from pydantic import PydanticDeprecationWarning
from uipath._cli._runtime._contracts import UiPathTraceContext

from ._events import CustomTraceEvents, FunctionCallEventData
from ._utils import _setup_tracer_httpx_logging, _simple_serialize_defaults

logger = logging.getLogger(__name__)

_setup_tracer_httpx_logging("/llmops_/api/Agent/trace/")


class Status:
    SUCCESS = 1
    ERROR = 2
    INTERRUPTED = 3


class AsyncUiPathTracer(AsyncBaseTracer):
    def __init__(
        self,
        context: Optional[UiPathTraceContext] = None,
        client: Optional[httpx.AsyncClient] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)

        self.client = client or httpx.AsyncClient()
        self.retries = 3
        self.log_queue: queue.Queue[dict[str, Any]] = queue.Queue()

        self.context = context or UiPathTraceContext()

        self.base_url = self._get_base_url()

        auth_token = env.get("UNATTENDED_USER_ACCESS_TOKEN") or env.get(
            "UIPATH_ACCESS_TOKEN"
        )

        self.headers = {"Authorization": f"Bearer {auth_token}"}

        self.running = True
        self.worker_task = asyncio.create_task(self._worker())
        self.function_call_run_map: Dict[str, Run] = {}

    async def on_custom_event(
        self,
        name: str,
        data: Any,
        *,
        run_id: uuid.UUID,
        tags=None,
        metadata=None,
        **kwargs: Any,
    ) -> None:
        if name == CustomTraceEvents.UIPATH_TRACE_FUNCTION_CALL:
            # only handle the function call event

            if not isinstance(data, FunctionCallEventData):
                logger.warning(
                    f"Received unexpected data type for function call event: {type(data)}"
                )
                return

            if data.event_type == "call":
                run = self.run_map[str(run_id)]
                child_run = run.create_child(
                    name=data.function_name,
                    run_type=data.run_type,
                    tags=data.tags,
                    inputs=data.inputs,
                )

                if data.metadata is not None:
                    run.add_metadata(data.metadata)

                call_uuid = data.call_uuid
                self.function_call_run_map[call_uuid] = child_run

                self._send_span(run)

            if data.event_type == "completion":
                call_uuid = data.call_uuid
                previous_run = self.function_call_run_map.pop(call_uuid, None)

                if previous_run:
                    previous_run.end(
                        outputs=self._safe_dict_dump(data.output), error=data.error
                    )
                    self._send_span(previous_run)

    async def wait_for_all_tracers(self) -> None:
        """
        Wait for all pending log requests to complete
        """
        self.running = False
        if self.worker_task:
            await self.worker_task

    async def _worker(self):
        """Worker loop that processes logs from the queue."""
        while self.running:
            try:
                if self.log_queue.empty():
                    await asyncio.sleep(1)
                    continue

                span_data = self.log_queue.get_nowait()

                url = self._build_url(self.context.trace_id)

                for attempt in range(self.retries):
                    response = await self.client.post(
                        url,
                        headers=self.headers,
                        json=[span_data],  # api expects a list of spans
                        timeout=10,
                    )

                    if response.is_success:
                        break

                    await asyncio.sleep(0.5 * (2**attempt))  # Exponential backoff

                    if 400 <= response.status_code < 600:
                        logger.warning(
                            f"Error when sending trace: {response}. Body is: {response.text}"
                        )
            except Exception as e:
                logger.warning(f"Exception when sending trace: {e}", exc_info=e)

        # wait for a bit to ensure all logs are sent
        await asyncio.sleep(1)

        # try to send any remaining logs in the queue
        while True:
            try:
                if self.log_queue.empty():
                    break

                span_data = self.log_queue.get_nowait()
                url = self._build_url(self.context.trace_id)

                response = await self.client.post(
                    url,
                    headers=self.headers,
                    json=[span_data],  # api expects a list of spans
                    timeout=10,
                )
            except Exception as e:
                logger.warning(f"Exception when sending trace: {e}", exc_info=e)

    async def _persist_run(self, run: Run) -> None:
        # Determine if this is a start or end trace based on whether end_time is set
        self._send_span(run)

    def _send_span(self, run: Run) -> None:
        """Send span data for a run to the API"""
        run_id = str(run.id)

        try:
            start_time = (
                run.start_time.isoformat() if run.start_time is not None else None
            )
            end_time = (
                run.end_time.isoformat() if run.end_time is not None else start_time
            )

            parent_id = (
                str(run.parent_run_id)
                if run.parent_run_id is not None
                else self.context.parent_span_id
            )
            attributes = self._safe_jsons_dump(self._run_to_dict(run))
            status = self._determine_status(run.error)

            span_data = {
                "id": run_id,
                "parentId": parent_id,
                "traceId": self.context.trace_id,
                "name": run.name,
                "startTime": start_time,
                "endTime": end_time,
                "referenceId": self.context.reference_id,
                "attributes": attributes,
                "organizationId": self.context.org_id,
                "tenantId": self.context.tenant_id,
                "spanType": "LangGraphRun",
                "status": status,
                "jobKey": self.context.job_id,
                "folderKey": self.context.folder_key,
                "processKey": self.context.folder_key,
                "expiryTimeUtc": None,
            }

            self.log_queue.put(span_data)
        except Exception as e:
            logger.warning(f"Exception when adding trace to queue: {e}.")

    async def _start_trace(self, run: Run) -> None:
        await super()._start_trace(run)
        await self._persist_run(run)

    async def _end_trace(self, run: Run) -> None:
        await super()._end_trace(run)
        await self._persist_run(run)

    def _determine_status(self, error: Optional[str]):
        if error:
            if error.startswith("GraphInterrupt("):
                return Status.INTERRUPTED

            return Status.ERROR

        return Status.SUCCESS

    def _safe_jsons_dump(self, obj) -> str:
        try:
            json_str = json.dumps(obj, default=_simple_serialize_defaults)
            return json_str
        except Exception as e:
            logger.warning(f"Error serializing object to JSON: {e}")
            return "{ }"

    def _safe_dict_dump(self, obj) -> Dict[str, Any]:
        try:
            serialized = json.loads(json.dumps(obj, default=_simple_serialize_defaults))
            return serialized
        except Exception as e:
            # Last resort - string representation
            logger.warning(f"Error serializing object to JSON: {e}")
            return {"raw": str(obj)}

    def _run_to_dict(self, run: Run):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=PydanticDeprecationWarning)

            return {
                **run.dict(exclude={"child_runs", "inputs", "outputs", "serialized"}),
                "inputs": run.inputs.copy() if run.inputs is not None else None,
                "outputs": run.outputs.copy() if run.outputs is not None else None,
            }

    def _get_base_url(self) -> str:
        uipath_url = (
            env.get("UIPATH_URL") or "https://cloud.uipath.com/dummyOrg/dummyTennant/"
        )

        uipath_url = uipath_url.rstrip("/")

        return uipath_url

    def _build_url(self, trace_id: Optional[str]) -> str:
        """Construct the URL for the API request."""
        return f"{self.base_url}/llmopstenant_/api/Traces/spans?traceId={trace_id}&source=Robots"
