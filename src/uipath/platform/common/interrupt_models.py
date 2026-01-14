"""Models for interrupt operations in UiPath platform."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..action_center.tasks import Task
from ..context_grounding import (
    BatchTransformCreationResponse,
    BatchTransformOutputColumn,
    CitationMode,
    DeepRagCreationResponse,
)
from ..documents import FileContent, StartExtractionResponse
from ..orchestrator.job import Job


class InvokeProcess(BaseModel):
    """Model representing a process invocation."""

    name: str
    process_folder_path: str | None = None
    process_folder_key: str | None = None
    input_arguments: dict[str, Any] | None


class WaitJob(BaseModel):
    """Model representing a wait job operation."""

    job: Job
    process_folder_path: str | None = None
    process_folder_key: str | None = None


class CreateTask(BaseModel):
    """Model representing an action creation."""

    title: str
    data: dict[str, Any] | None = None
    assignee: str | None = ""
    app_name: str | None = None
    app_folder_path: str | None = None
    app_folder_key: str | None = None
    app_key: str | None = None


class CreateEscalation(CreateTask):
    """Model representing an escalation creation."""

    pass


class WaitTask(BaseModel):
    """Model representing a wait action operation."""

    action: Task
    app_folder_path: str | None = None
    app_folder_key: str | None = None


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
    index_folder_path: str | None = None
    index_folder_key: str | None = None


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
    index_folder_path: str | None = None
    index_folder_key: str | None = None


class DocumentExtraction(BaseModel):
    """Model representing a document extraction task creation."""

    project_name: str
    tag: str
    file: FileContent | None = None
    file_path: str | None = None

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    @model_validator(mode="after")
    def validate_exactly_one_file_source(self) -> "DocumentExtraction":
        """Validate that exactly one of file or file_path is provided."""
        if (self.file is None) == (self.file_path is None):
            raise ValueError(
                "Exactly one of 'file' or 'file_path' must be provided, not both or neither"
            )
        return self


class WaitDocumentExtraction(BaseModel):
    """Model representing a wait document extraction task creation."""

    extraction: StartExtractionResponse
