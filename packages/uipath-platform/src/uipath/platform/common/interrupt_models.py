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


class InvokeProcessRaw(InvokeProcess):
    """Model representing a raw process invocation (returns job without state validation)."""

    pass


class WaitJobRaw(WaitJob):
    """Model representing a raw wait job operation (returns job without state validation)."""

    pass


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
    app_name: str | None = None
    recipient: TaskRecipient | None = None


class WaitEscalation(WaitTask):
    """Model representing a wait escalation operation."""

    pass


class CreateDeepRag(BaseModel):
    """Model representing a Deep RAG task creation."""

    name: str
    index_name: Annotated[str, Field(max_length=512)] | None = None
    index_id: Annotated[str, Field(max_length=512)] | None = None
    prompt: Annotated[str, Field(max_length=250000)]
    glob_pattern: Annotated[str, Field(max_length=512, default="*")] = "**"
    citation_mode: CitationMode = CitationMode.SKIP
    index_folder_key: str | None = None
    index_folder_path: str | None = None
    is_ephemeral_index: bool | None = None

    @model_validator(mode="after")
    def validate_ephemeral_index_requires_index_id(self) -> "CreateDeepRag":
        """Validate that if it is an ephemeral index that it is using index id."""
        if self.is_ephemeral_index is True and self.index_id is None:
            raise ValueError("Index id must be provided for an ephemeral index")
        return self


class CreateDeepRagRaw(CreateDeepRag):
    """Model representing a Deep RAG task creation (returns the deep_rag without status validation)."""

    pass


class WaitDeepRag(BaseModel):
    """Model representing a wait Deep RAG task."""

    deep_rag: DeepRagCreationResponse
    index_folder_path: str | None = None
    index_folder_key: str | None = None


class WaitDeepRagRaw(WaitDeepRag):
    """Model representing a wait Deep RAG task (returns the deep_rag without status validation)."""

    pass


class CreateEphemeralIndex(BaseModel):
    """Model representing an Ephemeral Index task creation."""

    usage: EphemeralIndexUsage
    attachments: list[str]


class CreateEphemeralIndexRaw(CreateEphemeralIndex):
    """Model representing an Ephemeral Index task creation (returns the ephemeral index without status validation)."""

    pass


class WaitEphemeralIndex(BaseModel):
    """Model representing a wait Ephemeral Index task."""

    index: ContextGroundingIndex


class WaitEphemeralIndexRaw(WaitEphemeralIndex):
    """Model representing a wait Ephemeral Index task (returns the ephemeral index without status validation)."""

    pass


class CreateBatchTransform(BaseModel):
    """Model representing a Batch Transform task creation."""

    name: str
    index_name: str | None = None
    index_id: Annotated[str, Field(max_length=512)] | None = None
    prompt: Annotated[str, Field(max_length=250000)]
    output_columns: list[BatchTransformOutputColumn]
    storage_bucket_folder_path_prefix: Annotated[str | None, Field(max_length=512)] = (
        None
    )
    enable_web_search_grounding: bool = False
    destination_path: str
    index_folder_key: str | None = None
    index_folder_path: str | None = None
    is_ephemeral_index: bool | None = None

    @model_validator(mode="after")
    def validate_ephemeral_index_requires_index_id(self) -> "CreateBatchTransform":
        """Validate that if it is an ephemeral index that it is using index id."""
        if self.is_ephemeral_index is True and self.index_id is None:
            raise ValueError("Index id must be provided for an ephemeral index")
        return self


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
    task_url: str | None = None


class WaitIntegrationEvent(BaseModel):
    """Model representing a wait on an Integration Services event.

    Used to suspend a job until a remote event (e.g. Slack message, Teams reply)
    is delivered by Integration Services. The SDK resolves `connection_name`
    (scoped to `connection_folder_path` when provided) to the underlying
    connection id and generates a fresh `inbox_id` when the trigger is created;
    the rest of the fields describe which remote event to subscribe to via
    the Connections service.
    """

    connector: str
    connection_name: str
    connection_folder_path: str | None = None
    operation: str
    object_name: str
    filter_expression: str | None = None
    parameters: dict[str, str] | None = None
