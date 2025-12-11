"""Models for interrupt operations in UiPath platform."""

from typing import Annotated, Any, Dict, Optional

from pydantic import BaseModel, Field

from ..action_center import Task
from ..context_grounding import (
    BatchTransformCreationResponse,
    BatchTransformOutputColumn,
    CitationMode,
    DeepRagCreationResponse,
)
from ..orchestrator import Job


class InvokeProcess(BaseModel):
    """Model representing a process invocation."""

    name: str
    process_folder_path: Optional[str] = None
    process_folder_key: Optional[str] = None
    input_arguments: Optional[Dict[str, Any]]


class WaitJob(BaseModel):
    """Model representing a wait job operation."""

    job: Job
    process_folder_path: Optional[str] = None
    process_folder_key: Optional[str] = None


class CreateTask(BaseModel):
    """Model representing an action creation."""

    title: str
    data: Optional[Dict[str, Any]] = None
    assignee: Optional[str] = ""
    app_name: Optional[str] = None
    app_folder_path: Optional[str] = None
    app_folder_key: Optional[str] = None
    app_key: Optional[str] = None


class CreateEscalation(CreateTask):
    """Model representing an escalation creation."""

    pass


class WaitTask(BaseModel):
    """Model representing a wait action operation."""

    action: Task
    app_folder_path: Optional[str] = None
    app_folder_key: Optional[str] = None


class WaitEscalation(WaitTask):
    """Model representing a wait escalation operation."""

    pass


class CreateDeepRag(BaseModel):
    """Model representing a Deep RAG task creation."""

    name: str
    index_name: Annotated[str, Field(max_length=512)]
    prompt: Annotated[str, Field(max_length=250000)]
    glob_pattern: Annotated[str, Field(max_length=512, default="*")] = "**"
    citation_mode: CitationMode = CitationMode.SKIP
    index_folder_key: str | None = None
    index_folder_path: str | None = None


class WaitDeepRag(BaseModel):
    """Model representing a wait Deep RAG task."""

    deep_rag: DeepRagCreationResponse
    index_folder_path: Optional[str] = None
    index_folder_key: Optional[str] = None


class CreateBatchTransform(BaseModel):
    """Model representing a Batch Transform task creation."""

    name: str
    index_name: str
    prompt: Annotated[str, Field(max_length=250000)]
    output_columns: list[BatchTransformOutputColumn]
    storage_bucket_folder_path_prefix: Annotated[str | None, Field(max_length=512)] = (
        None
    )
    enable_web_search_grounding: bool = False
    destination_path: str
    index_folder_key: str | None = None
    index_folder_path: str | None = None


class WaitBatchTransform(BaseModel):
    """Model representing a wait Batch Transform task."""

    batch_transform: BatchTransformCreationResponse
    index_folder_path: Optional[str] = None
    index_folder_key: Optional[str] = None
