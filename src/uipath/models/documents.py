from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


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


class FieldValueProjection(BaseModel):
    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_alias=True,
    )

    id: str
    name: str
    value: str
    unformatted_value: str = Field(alias="unformattedValue")
    confidence: float
    ocr_confidence: float = Field(alias="ocrConfidence")
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
    tag: str
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
    tag: str
    document_type_id: str = Field(alias="documentTypeId")
    operation_id: str = Field(alias="operationId")


class ValidatedResult(BaseModel):
    """A model representing the result of a validation action.

    Attributes:
        document_id (str): The ID of the validated document.
        results_document (dict): The validated results document.
    """

    model_config = ConfigDict(
        serialize_by_alias=True,
        validate_by_alias=True,
    )

    document_id: str = Field(alias="DocumentId")
    results_document: dict = Field(alias="ResultsDocument")  # type: ignore
