from enum import Enum
from typing import Any, Dict, List, Optional, Type, Union, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, create_model


class ReferenceType(Enum):
    ManyToOne = "ManyToOne"


class FieldDisplayType(Enum):
    Basic = "Basic"
    Relationship = "Relationship"
    File = "File"
    ChoiceSetSingle = "ChoiceSetSingle"
    ChoiceSetMultiple = "ChoiceSetMultiple"
    AutoNumber = "AutoNumber"


class DataDirectionType(Enum):
    ReadOnly = "ReadOnly"
    ReadAndWrite = "ReadAndWrite"


class JoinType(Enum):
    LeftJoin = "LeftJoin"


class EntityType(Enum):
    Entity = "Entity"
    ChoiceSet = "ChoiceSet"
    InternalEntity = "InternalEntity"
    SystemEntity = "SystemEntity"


class EntityFieldMetadata(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
    )
    type: str
    required: bool
    name: str


class ExternalConnection(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )
    id: str
    connection_id: str = Field(alias="connectionId")
    element_instance_id: str = Field(alias="elementInstanceId")
    folder_id: str = Field(alias="folderKey")  # named folderKey in TS SDK
    connector_id: str = Field(alias="connectorKey")  # named connectorKey in TS SDK
    connector_name: str = Field(alias="connectorName")
    connection_name: str = Field(alias="connectionName")


class ExternalFieldMapping(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )
    id: str
    external_field_name: str = Field(alias="externalFieldName")
    external_field_display_name: str = Field(alias="externalFieldDisplayName")
    external_object_id: str = Field(alias="externalObjectId")
    external_field_type: str = Field(alias="externalFieldType")
    internal_field_id: str = Field(alias="internalFieldId")
    direction_type: DataDirectionType = Field(alias="directionType")


class FieldDataType(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )
    name: str
    length_limit: Optional[int] = Field(default=None, alias="LengthLimit")
    max_value: Optional[int] = Field(default=None, alias="MaxValue")
    min_value: Optional[int] = Field(default=None, alias="MinValue")
    decimal_precision: Optional[int] = Field(default=None, alias="DecimalPrecision")


class FieldMetadata(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )
    id: Optional[str] = Field(default=None, alias="id")
    name: str
    is_primary_key: bool = Field(alias="isPrimaryKey")
    is_foreign_key: bool = Field(alias="isForeignKey")
    is_external_field: bool = Field(alias="isExternalField")
    is_hidden_field: bool = Field(alias="isHiddenField")
    is_unique: bool = Field(alias="isUnique")
    reference_name: Optional[str] = Field(default=None, alias="referenceName")
    reference_entity: Optional["Entity"] = Field(default=None, alias="referenceEntity")
    reference_choiceset: Optional["Entity"] = Field(
        default=None, alias="referenceChoiceset"
    )
    reference_field: Optional["EntityField"] = Field(
        default=None, alias="referenceField"
    )
    reference_type: ReferenceType = Field(alias="referenceType")
    sql_type: "FieldDataType" = Field(alias="sqlType")
    is_required: bool = Field(alias="isRequired")
    display_name: str = Field(alias="displayName")
    description: Optional[str] = Field(default=None, alias="description")
    is_system_field: bool = Field(alias="isSystemField")
    field_display_type: Optional[str] = Field(
        default=None, alias="fieldDisplayType"
    )  # Should be FieldDisplayType enum
    choiceset_id: Optional[str] = Field(default=None, alias="choicesetId")
    default_value: Optional[str] = Field(default=None, alias="defaultValue")
    is_attachment: bool = Field(alias="isAttachment")
    is_rbac_enabled: bool = Field(alias="isRbacEnabled")


class ExternalField(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )
    field_metadata: FieldMetadata = Field(alias="fieldMetadata")
    external_field_mapping_detail: ExternalFieldMapping = Field(
        alias="externalFieldMappingDetail"
    )


class EntityField(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
    )
    id: Optional[str] = Field(default=None, alias="id")
    definition: Optional[FieldMetadata] = Field(default=None, alias="definition")


class ExternalObject(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )
    id: str
    external_object_name: str = Field(alias="externalObjectName")
    external_object_display_name: str = Field(alias="externalObjectDisplayName")
    primary_key: str = Field(alias="primaryKey")
    external_connection_id: str = Field(alias="externalConnectionId")
    entity_id: str = Field(alias="entityId")
    is_primary_source: bool = Field(alias="isPrimarySource")


class ExternalSourceFields(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )
    fields: List[ExternalField]
    external_object_detail: ExternalObject = Field(alias="externalObject")
    external_connection_detail: ExternalConnection = Field(alias="externalConnection")


class SourceJoinCriteria(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )
    id: str
    entity_id: str = Field(alias="entityId")
    join_field_name: str = Field(alias="joinFieldName")
    join_type: str = Field(alias="joinType")
    related_source_object_id: str = Field(alias="relatedSourceObjectId")
    related_source_object_field_name: str = Field(alias="relatedSourceObjectFieldName")
    related_source_field_name: str = Field(alias="relatedSourceFieldName")


class EntityRecord(BaseModel):
    model_config = {
        "validate_by_name": True,
        "validate_by_alias": True,
        "extra": "allow",
    }

    id: str = Field(alias="Id")  # Mandatory field validated by Pydantic

    @classmethod
    def from_data(
        cls, data: Dict[str, Any], model: Optional[Any] = None
    ) -> "EntityRecord":
        """Create an EntityRecord instance by validating raw data and optionally instantiating a custom model.

        :param data: Raw data dictionary for the entity.
        :param model: Optional user-defined class for validation.
        :return: EntityRecord instance
        """
        # Validate the "Id" field is mandatory and must be a string
        id_value = data.get("Id", None)
        if id_value is None or not isinstance(id_value, str):
            raise ValueError("Field 'Id' is mandatory and must be a string.")

        if model:
            # Check if the model is a plain Python class or Pydantic model
            cls._validate_against_user_model(data, model)

        return cls(**data)

    @staticmethod
    def _validate_against_user_model(
        data: Dict[str, Any], user_class: Type[Any]
    ) -> None:
        user_class_annotations = getattr(user_class, "__annotations__", None)
        if user_class_annotations is None:
            raise ValueError(
                f"User-provided class '{user_class.__name__}' is missing type annotations."
            )

        # Dynamically define a Pydantic model based on the user's class annotations
        # Fields must be valid type annotations directly
        pydantic_fields = {}

        for name, annotation in user_class_annotations.items():
            is_optional = False

            origin = get_origin(annotation)
            args = get_args(annotation)

            # Handle Optional[...] or X | None
            if origin is Union and type(None) in args:
                is_optional = True

            # Check for optional fields
            if is_optional:
                pydantic_fields[name] = (annotation, None)  # Not required
            else:
                pydantic_fields[name] = (annotation, ...)  # type: ignore

        # Dynamically create the Pydantic model class
        dynamic_model = create_model(
            f"Dynamic_{user_class.__name__}",
            **pydantic_fields,  # type: ignore
        )

        # Validate input data
        dynamic_model.model_validate(data)


class Entity(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )

    name: str
    display_name: str = Field(alias="displayName")
    entity_type: str = Field(alias="entityType")
    description: Optional[str] = Field(default=None, alias="description")
    fields: Optional[List[FieldMetadata]] = Field(default=None, alias="fields")
    external_fields: Optional[List[ExternalSourceFields]] = Field(
        default=None, alias="externalFields"
    )
    source_join_criteria: Optional[List[SourceJoinCriteria]] = Field(
        default=None, alias="sourceJoinCriteria"
    )
    record_count: Optional[int] = Field(default=None, alias="recordCount")
    storage_size_in_mb: Optional[float] = Field(default=None, alias="storageSizeInMB")
    used_storage_size_in_mb: Optional[float] = Field(
        default=None, alias="usedStorageSizeInMB"
    )
    attachment_size_in_byte: Optional[int] = Field(
        default=None, alias="attachmentSizeInBytes"
    )
    is_rbac_enabled: bool = Field(alias="isRbacEnabled")
    id: str


class EntityRecordsBatchResponse(BaseModel):
    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )

    success_records: List[EntityRecord] = Field(alias="successRecords")
    failure_records: List[EntityRecord] = Field(alias="failureRecords")


Entity.model_rebuild()
