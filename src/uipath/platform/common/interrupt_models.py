"""Models for interrupt operations in UiPath platform."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from uipath.platform.context_grounding.context_grounding_index import (
    ContextGroundingIndex,
)

from ..action_center.tasks import Task, TaskRecipient
from ..attachments import Attachment
from ..context_grounding import (
    BatchTransformCreationResponse,
    BatchTransformOutputColumn,
    CitationMode,
    DeepRagCreationResponse,
    EphemeralIndexUsage,
)
from ..documents import (
    ActionPriority,
    ExtractionResponseIXP,
    FileContent,
    StartExtractionResponse,
)
from ..documents.documents import StartExtractionValidationResponse
from ..orchestrator.job import Job


class InvokeProcess(BaseModel):
    """Model representing a process invocation."""

    name: str
    process_folder_path: str | None = None
    process_folder_key: str | None = None
    input_arguments: dict[str, Any] | None
    attachments: list[Attachment] | None = None


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
    recipient: TaskRecipient | None = None
    app_name: str | None = None
    app_folder_path: str | None = None
    app_folder_key: str | None = None
    app_key: str | None = None
    priority: str | None = None
    labels: list[str] | None = None
    is_actionable_message_enabled: bool | None = None
    actionable_message_metadata: dict[str, Any] | None = None
    source_name: str = "Agent"


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


class CreateEphemeralIndex(BaseModel):
    """Model representing a Ephemeral Index task creation."""

    usage: EphemeralIndexUsage
    attachments: list[str]


class WaitEphemeralIndex(BaseModel):
    """Model representing a wait Ephemeral Index task."""

    index: ContextGroundingIndex


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


class InvokeSystemAgent(BaseModel):
    """Model representing a system agent job invocation."""

    agent_name: str
    entrypoint: str
    input_arguments: dict[str, Any] | None = None
    folder_path: str | None = None
    folder_key: str | None = None


class WaitSystemAgent(BaseModel):
    """Model representing a wait system agent job invocation."""

    job_key: str
    process_folder_path: str | None = None
    process_folder_key: str | None = None


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


class DocumentExtractionValidation(BaseModel):
    """Model representing a document extraction task creation."""

    extraction_response: ExtractionResponseIXP
    action_title: str
    action_catalog: str | None = None
    action_priority: ActionPriority | None = None
    action_folder: str | None = None
    storage_bucket_name: str | None = None
    storage_bucket_directory_path: str | None = None


class WaitDocumentExtractionValidation(BaseModel):
    """Model representing a wait document extraction task creation."""

    extraction_validation: StartExtractionValidationResponse
