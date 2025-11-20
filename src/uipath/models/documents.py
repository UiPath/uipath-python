from enum import Enum
from typing import IO, List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

FileContent = Union[IO[bytes], bytes, str]


class FieldType(str, Enum):
    TEXT = "Text"
    NUMBER = "Number"
    DATE = "Date"
    NAME = "Name"
    ADDRESS = "Address"
    KEYWORD = "Keyword"
    SET = "Set"
    BOOLEAN = "Boolean"
    TABLE = "Table"
    INTERNAL = "Internal"


class ActionPriority(str, Enum):
    """Priority levels for validation actions. More details can be found in the [official documentation](https://docs.uipath.com/action-center/automation-cloud/latest/user-guide/create-document-validation-action#configuration)."""

    LOW = "Low"
    """Low priority"""
    MEDIUM = "Medium"
    """Medium priority"""
    HIGH = "High"
    """High priority"""
    CRITICAL = "Critical"
    """Critical priority"""


class ProjectType(str, Enum):
    """Project types available and supported by Documents Service."""

    IXP = "IXP"
    """Represents an [IXP](https://docs.uipath.com/ixp/automation-cloud/latest/overview/managing-projects#creating-a-new-project) project type."""
    MODERN = "Modern"
    """Represents a [DU Modern](https://docs.uipath.com/document-understanding/automation-cloud/latest/user-guide/about-document-understanding) project type."""
    PRETRAINED = "Pretrained"
    """Represents a [Pretrained](https://docs.uipath.com/document-understanding/automation-cloud/latest/user-guide/out-of-the-box-pre-trained-ml-packages) project type."""


class FieldValueProjection(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_alias=True,
    )

    id: str
    name: str
    value: Optional[str]
    unformatted_value: Optional[str] = Field(alias="unformattedValue")
    confidence: Optional[float]
    ocr_confidence: Optional[float] = Field(alias="ocrConfidence")
    type: FieldType


class FieldGroupValueProjection(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_alias=True,
    )

    field_group_name: str = Field(alias="fieldGroupName")
    field_values: List[FieldValueProjection] = Field(alias="fieldValues")


class ExtractionResult(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_alias=True,
    )

    document_id: str = Field(alias="DocumentId")
    results_version: int = Field(alias="ResultsVersion")
    results_document: dict = Field(alias="ResultsDocument")  # type: ignore
    extractor_payloads: Optional[List[dict]] = Field(  # type: ignore
        default=None, alias="ExtractorPayloads"
    )
    business_rules_results: Optional[List[dict]] = Field(  # type: ignore
        default=None, alias="BusinessRulesResults"
    )


class ExtractionResponse(BaseModel):
    """A model representing the response from a document extraction process.

    Attributes:
        extraction_result (ExtractionResult): The result of the extraction process.
        project_id (str): The ID of the project associated with the extraction.
        tag (str): The tag associated with the published model version.
        document_type_id (str): The ID of the document type associated with the extraction.
    """

    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_alias=True,
    )

    extraction_result: ExtractionResult = Field(alias="extractionResult")
    project_id: str = Field(alias="projectId")
    project_type: ProjectType = Field(alias="projectType")
    tag: Optional[str]
    document_type_id: str = Field(alias="documentTypeId")


class ExtractionResponseIXP(ExtractionResponse):
    """A model representing the response from a document extraction process for IXP projects.

    Attributes:
        data_projection (List[FieldGroupValueProjection]): A simplified projection of the extracted data.
    """

    data_projection: List[FieldGroupValueProjection] = Field(alias="dataProjection")


class ValidationAction(BaseModel):
    """A model representing a validation action for a document.

    Attributes:
        action_data (dict): The data associated with the validation action.
        action_status (str): The status of the validation action. Possible values can be found in the [official documentation](https://docs.uipath.com/action-center/automation-cloud/latest/user-guide/about-actions#action-statuses).
        project_id (str): The ID of the project associated with the validation action.
        tag (str): The tag associated with the published model version.
        operation_id (str): The operation ID associated with the validation action.
    """

    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_alias=True,
    )

    action_data: dict = Field(alias="actionData")  # type: ignore
    action_status: str = Field(alias="actionStatus")
    project_id: str = Field(alias="projectId")
    project_type: ProjectType = Field(alias="projectType")
    tag: Optional[str]
    operation_id: str = Field(alias="operationId")


class ValidateClassificationAction(ValidationAction):
    pass


class ValidateExtractionAction(ValidationAction):
    document_type_id: str = Field(alias="documentTypeId")


class Reference(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_alias=True,
    )

    text_start_index: int = Field(alias="TextStartIndex")
    text_length: int = Field(alias="TextLength")
    tokens: List[str] = Field(alias="Tokens")


class DocumentBounds(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_alias=True,
    )

    start_page: int = Field(alias="StartPage")
    page_count: int = Field(alias="PageCount")
    text_start_index: int = Field(alias="TextStartIndex")
    text_length: int = Field(alias="TextLength")
    page_range: str = Field(alias="PageRange")


class ClassificationResult(BaseModel):
    """A model representing the result of a document classification.

    Attributes:
        document_id (str): The ID of the classified document.
        document_type_id (str): The ID of the predicted document type.
        confidence (float): The confidence score of the classification.
        ocr_confidence (float): The OCR confidence score of the document.
        reference (Reference): The reference information for the classified document.
        document_bounds (DocumentBounds): The bounds of the document in terms of pages and text.
        classifier_name (str): The name of the classifier used.
        project_id (str): The ID of the project associated with the classification.
    """

    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_alias=True,
    )

    document_id: str = Field(alias="DocumentId")
    document_type_id: str = Field(alias="DocumentTypeId")
    confidence: float = Field(alias="Confidence")
    ocr_confidence: float = Field(alias="OcrConfidence")
    reference: Reference = Field(alias="Reference")
    document_bounds: DocumentBounds = Field(alias="DocumentBounds")
    classifier_name: str = Field(alias="ClassifierName")
    project_id: str = Field(alias="ProjectId")
    project_type: ProjectType = Field(alias="ProjectType")
    tag: Optional[str] = Field(alias="Tag")


class ClassificationResponse(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_alias=True,
    )

    classification_results: List[ClassificationResult] = Field(
        alias="classificationResults"
    )
