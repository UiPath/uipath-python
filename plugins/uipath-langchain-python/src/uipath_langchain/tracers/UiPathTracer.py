import json
import logging
import re
import uuid
import warnings
from os import environ as env
from time import sleep

import httpx
from langchain_core.tracers.base import BaseTracer
from langchain_core.tracers.schemas import Run
from pydantic import PydanticDeprecationWarning

from ._utils import _simple_serialize_defaults

logger = logging.getLogger(__name__)


class UiPathTracer(BaseTracer):
    def __init__(self, client, **kwargs):
        super().__init__(**kwargs)

        self.client = client or httpx.Client()
        self.retries = 3

        llm_ops_pattern = self._get_base_url() + "{orgId}/llmops_"
        self.orgId = env.get("UIPATH_ORGANIZATION_ID")
        self.tenantId = env.get("UIPATH_TENANT_ID")
        self.url = llm_ops_pattern.format(orgId=self.orgId).rstrip("/")

        self.auth_token = env.get("UNATTENDED_USER_ACCESS_TOKEN") or env.get(
            "UIPATH_ACCESS_TOKEN"
        )

        self.jobKey = env.get("UIPATH_JOB_KEY")
        self.folderKey = env.get("UIPATH_FOLDER_KEY")
        self.processKey = env.get("UIPATH_PROCESS_UUID")

        self.referenceId = self.jobKey or str(uuid.uuid4())

        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
        }

    def _get_base_url(self) -> str:
        uipath_url = (
            env.get("UIPATH_URL") or "https://cloud.uipath.com/dummyOrg/dummyTennant/"
        )
        uipath_url = uipath_url.rstrip("/")

        # split by "//" to get ['', 'https:', 'alpha.uipath.com/ada/byoa']
        parts = uipath_url.split("//")

        # after splitting by //, the base URL will be at index 1 along with the rest,
        # hence split it again using "/" to get ['https:', 'alpha.uipath.com', 'ada', 'byoa']
        base_url_parts = parts[1].split("/")

        # combine scheme and netloc to get the base URL
        base_url = parts[0] + "//" + base_url_parts[0] + "/"

        return base_url

    def init_trace(self, run_name, trace_id=None) -> None:
        trace_id_env = env.get("UIPATH_TRACE_ID")

        if trace_id_env:
            self.trace_parent = trace_id_env
        else:
            self.start_trace(run_name, trace_id)

    def start_trace(self, run_name, trace_id=None) -> None:
        self.trace_parent = trace_id or str(uuid.uuid4())
        run_name = run_name or f"Job Run: {self.trace_parent}"
        trace_data = {
            "id": self.trace_parent,
            "name": re.sub(
                r"[!@#$<>\.]", "", run_name
            ),  # if we use these characters the Agents UI throws some error (but llmops backend seems fine)
            "referenceId": self.referenceId,
            "attributes": "{}",
            "organizationId": self.orgId,
            "tenantId": self.tenantId,
        }

        for attempt in range(self.retries):
            response = self.client.post(
                f"{self.url}/api/Agent/trace/", headers=self.headers, json=trace_data
            )

            if response.is_success:
                break

            sleep(0.5 * (2**attempt))  # Exponential backoff

        if 400 <= response.status_code < 600:
            logger.warning(
                f"Error when sending trace: {response}. Body is: {response.text}"
            )

    def _persist_run(self, run: Run) -> None:
        # when (run.id == run.parent_run_id)  it's the start of a new trace
        # but we treat all as spans and parent to a single Trace with Id == Job.Key
        start_time = run.start_time.isoformat() if run.start_time is not None else None
        end_time = run.end_time.isoformat() if run.end_time is not None else start_time

        span_data = {
            "id": str(run.id),
            "parentId": str(run.parent_run_id)
            if run.parent_run_id is not None
            else None,
            "traceId": self.trace_parent,
            "name": run.name,
            "startTime": start_time,
            "endTime": end_time,
            "referenceId": self.referenceId,
            "attributes": self._safe_json_dump(self._run_to_dict(run)),
            "organizationId": self.orgId,
            "tenantId": self.tenantId,
            "spanType": "LangGraphRun",
            "status": 2 if run.error else 1,
            "jobKey": self.jobKey,
            "folderKey": self.folderKey,
            "processKey": self.processKey,
        }

        for attempt in range(self.retries):
            response = self.client.post(
                f"{self.url}/api/Agent/span/", headers=self.headers, json=span_data
            )

            if response.is_success:
                break

            sleep(0.5 * (2**attempt))  # Exponential backoff

        if 400 <= response.status_code < 600:
            logger.warning(
                f"Error when sending trace: {response}. Body is: {response.text}"
            )

    def _end_trace(self, run: Run) -> None:
        super()._end_trace(run)
        self._persist_run(run)

    def _safe_json_dump(self, obj) -> str:
        try:
            json_str = json.dumps(obj, default=_simple_serialize_defaults)
            return json_str
        except Exception as e:
            logger.warning(e)
            return "{ }"

    def _run_to_dict(self, run: Run):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=PydanticDeprecationWarning)

            return {
                **run.dict(exclude={"child_runs", "inputs", "outputs"}),
                "inputs": run.inputs.copy() if run.inputs is not None else None,
                "outputs": run.outputs.copy() if run.outputs is not None else None,
            }
