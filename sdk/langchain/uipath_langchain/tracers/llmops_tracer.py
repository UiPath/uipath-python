import json
import os
import uuid
import logging
import warnings
from pydantic import PydanticDeprecationWarning
import requests
from langchain_core.tracers.base import BaseTracer
from langchain_core.tracers.schemas import Run
import re

logger = logging.getLogger(__name__)

class LlmopsTracer(BaseTracer):
    def __init__(self, verify_https = True, **kwargs):
        super().__init__(**kwargs)

        # usefull when testing
        self.verify_https = verify_https
        llm_ops_pattern = os.getenv("UIPATH_LLMOPS_ENDPOINT_FORMAT") or "https://cloud.uipath.com/{orgId}/llmops_/"
        self.orgId = os.getenv("UIPATH_ORGANIZATION_ID")
        self.tenantId = os.getenv("UIPATH_TENANT_ID")
        self.agentId = os.getenv("UIPATH_AGENT_ID")
        self.url = llm_ops_pattern.format(orgId = self.orgId).rstrip("/")

        auth_token = os.getenv("UIPATH_LLM_OPS_ACCESS_TOKEN")

        self.headers = {
            'Authorization': f'Bearer {auth_token}',
        }

    def start_trace(self, run_name, trace_id = None) -> None:
        self.trace_parent = trace_id or str(uuid.uuid4())
        run_name = run_name or f"Job Run: {self.trace_parent}" 
        trace_data = {
            "id": self.trace_parent,
            "name": re.sub('[!@#$<>\.]', '', run_name), # if we use these characters the Agents UI throws some error (but llmops backend seems fine)
            "referenceId": self.agentId,
            "attributes": "{}",
            "organizationId": self.orgId,
            "tenantId": self.tenantId
        }

        response = requests.post(
            f'{self.url}/api/Agent/trace/', 
            headers=self.headers, 
            verify=self.verify_https,
            json=trace_data
        )

        if 400 <= response.status_code < 600:
            logger.warning(f"Error when sending trace: {response}")

    def _persist_run(self, run: Run) -> None:
        # when (run.id == run.parent_run_id)  it's the start of a new trace
        # but we treat all as spans and parent to a single Trace with Id == Job.Key

        span_data = {
            "id": str(run.id),
            "parentId": str(run.parent_run_id) if run.parent_run_id is not None else None,
            "traceId": self.trace_parent, # str(run.trace_id),
            "name": run.name,
            "startTime": str(run.start_time),
            "endTime": str(run.end_time or run.start_time),
            "referenceId": self.agentId,
            "attributes": self._safe_json_dump(self._run_to_dict(run)),
            "organizationId": self.orgId,
            "tenantId": self.tenantId
        }

        response = requests.post(
            f'{self.url}/api/Agent/span/', 
            headers=self.headers, 
            verify=self.verify_https,
            json=span_data
        )

        if 400 <= response.status_code < 600:
            logger.warning(f"Error when sending trace: {response}")

    def _end_trace(self, run: Run) -> None:
        super()._end_trace(run)
        self._persist_run(run)

    def _safe_json_dump(self, obj) -> str:
        try:
            json_str = json.dumps(obj, default=str)
            return json_str
        except Exception as e:
            logger.warning(e)
            return "{ }"
        
    def _run_to_dict(self, run: Run) -> dict:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=PydanticDeprecationWarning)

            return {
                **run.dict(exclude={"child_runs", "inputs", "outputs"}),
                "inputs": run.inputs.copy() if run.inputs is not None else None,
                "outputs": run.outputs.copy() if run.outputs is not None else None,
            }
