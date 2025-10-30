from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from uipath.utils.dynamic_schema import jsonschema_to_pydantic


def atest_dynamic_schema():
    # Arrange
    class InnerSchema(BaseModel):
        """Inner schema description including a self-reference."""

        self_reference: Optional["InnerSchema"] = None

    class CustomEnum(str, Enum):
        KEY_1 = "VALUE_1"
        KEY_2 = "VALUE_2"

    class Schema(BaseModel):
        """Schema description."""

        string: str = Field(
            default="", title="String Title", description="String Description"
        )
        optional_string: Optional[str] = Field(
            default=None,
            title="Optional String Title",
            description="Optional String Description",
        )
        list_str: List[str] = Field(
            default=[], title="List String", description="List String Description"
        )

        integer: int = Field(
            default=0, title="Integer Title", description="Integer Description"
        )
        optional_integer: Optional[int] = Field(
            default=None,
            title="Option Integer Title",
            description="Option Integer Description",
        )
        list_integer: List[int] = Field(
            default=[],
            title="List Integer Title",
            description="List Integer Description",
        )

        floating: float = Field(
            default=0.0, title="Floating Title", description="Floating Description"
        )
        optional_floating: Optional[float] = Field(
            default=None,
            title="Option Floating Title",
            description="Option Floating Description",
        )
        list_floating: List[float] = Field(
            default=[],
            title="List Floating Title",
            description="List Floating Description",
        )

        boolean: bool = Field(
            default=False, title="Boolean Title", description="Boolean Description"
        )
        optional_boolean: Optional[bool] = Field(
            default=None,
            title="Option Boolean Title",
            description="Option Boolean Description",
        )
        list_boolean: List[bool] = Field(
            default=[],
            title="List Boolean Title",
            description="List Boolean Description",
        )

        nested_object: InnerSchema = Field(
            default=InnerSchema(self_reference=None),
            title="Nested Object Title",
            description="Nested Object Description",
        )
        optional_nested_object: Optional[InnerSchema] = Field(
            default=None,
            title="Optional Nested Object Title",
            description="Optional Nested Object Description",
        )
        list_nested_object: List[InnerSchema] = Field(
            default=[],
            title="List Nested Object Title",
            description="List Nested Object Description",
        )

        enum: CustomEnum = Field(
            default=CustomEnum.KEY_1,
            title="Enum Title",
            description="Enum Description",
        )

    schema_json = Schema.model_json_schema()

    # Act
    dynamic_schema = jsonschema_to_pydantic(schema_json)
    dynamic_schema_json = dynamic_schema.model_json_schema()

    # Assert
    assert dynamic_schema_json == schema_json
