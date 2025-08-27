from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


def _snake_to_camel_case(snake_str: str) -> str:
    """Convert snake_case string to camelCase."""
    components = snake_str.split("_")
    return components[0] + "".join(x.title() for x in components[1:])


def _snake_to_pascal_case(snake_str: str) -> str:
    """Convert snake_case string to PascalCase."""
    components = snake_str.split("_")
    return "".join(x.title() for x in components)


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
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


class FieldValueProjection(BaseModel):
    model_config = ConfigDict(
        alias_generator=_snake_to_camel_case, serialize_by_alias=True
    )

    id: str
    name: str
    value: str
    unformatted_value: str
    confidence: float
    ocr_confidence: float
    type: FieldType


class FieldGroupValueProjection(BaseModel):
    model_config = ConfigDict(
        alias_generator=_snake_to_camel_case, serialize_by_alias=True
    )

    field_group_name: str
    field_values: List[FieldValueProjection]


class ExtractionResult(BaseModel):
    model_config = ConfigDict(
        alias_generator=_snake_to_pascal_case, serialize_by_alias=True
    )

    document_id: str
    results_version: int
    results_document: dict
    extractor_payloads: Optional[List[dict]] = None
    business_rules_results: Optional[List[dict]] = None


class ExtractionResponse(BaseModel):
    """A model representing the response from a document extraction process.

    Attributes:
        extraction_result (ExtractionResult): The result of the extraction process.
        data_projection (List[FieldGroupValueProjection]): A simplified projection of the extracted data.
        project_id (str): The ID of the project associated with the extraction.
        tag (str): The tag associated with the published model version.
    """

    model_config = ConfigDict(
        alias_generator=_snake_to_camel_case, serialize_by_alias=True
    )

    extraction_result: ExtractionResult
    data_projection: List[FieldGroupValueProjection]
    project_id: str
    tag: str


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
        alias_generator=_snake_to_camel_case, serialize_by_alias=True
    )

    action_data: dict
    action_status: str
    project_id: str
    tag: str
    operation_id: str


class ValidatedResult(BaseModel):
    """A model representing the result of a validation action.

    Attributes:
        document_id (str): The ID of the validated document.
        results_document (dict): The validated results document.
    """

    model_config = ConfigDict(
        alias_generator=_snake_to_pascal_case, serialize_by_alias=True
    )

    document_id: str
    results_document: dict
