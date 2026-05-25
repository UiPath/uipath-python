"""Entities models for UiPath Platform API interactions."""

from __future__ import annotations

from enum import Enum, IntEnum
from types import EllipsisType
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Type,
    Union,
    get_args,
    get_origin,
    overload,
)

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    create_model,
    model_validator,
)

if TYPE_CHECKING:
    from ._entities_service import EntitiesService


class ReferenceType(Enum):
    """Enum representing types of references between entities."""

    ManyToOne = "ManyToOne"


class FieldDisplayType(Enum):
    """Enum representing display types of fields in entities."""

    Basic = "Basic"
    Relationship = "Relationship"
    File = "File"
    ChoiceSetSingle = "ChoiceSetSingle"
    ChoiceSetMultiple = "ChoiceSetMultiple"
    AutoNumber = "AutoNumber"


class DataDirectionType(Enum):
    """Enum representing data direction types for fields in entities."""

    ReadOnly = "ReadOnly"
    ReadAndWrite = "ReadAndWrite"


class JoinType(Enum):
    """Enum representing types of joins between entities."""

    LeftJoin = "LeftJoin"


class EntityType(Enum):
    """Enum representing types of entities."""

    Entity = "Entity"
    ChoiceSet = "ChoiceSet"
    InternalEntity = "InternalEntity"
    SystemEntity = "SystemEntity"


class EntityFieldMetadata(BaseModel):
    """Model representing metadata for an entity field."""

    model_config = ConfigDict(
        validate_by_name=True,
    )
    type: str
    required: bool
    name: str


class ExternalConnection(BaseModel):
    """Model representing an external connection."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )
    id: str
    connection_id: str = Field(alias="connectionId")
    element_instance_id: str = Field(alias="elementInstanceId")
    folder_id: str = Field(alias="folderKey")
    connector_id: str = Field(alias="connectorKey")
    connector_name: str = Field(alias="connectorName")
    connection_name: str = Field(alias="connectionName")


class ExternalFieldMapping(BaseModel):
    """Model representing an external field mapping."""

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
    """Model representing data type information for a field."""

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
    """Model representing metadata for an entity field."""

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
    reference_type: Optional[ReferenceType] = Field(default=None, alias="referenceType")
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
    """Model representing an external field."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )
    field_metadata: FieldMetadata = Field(alias="fieldMetadata")
    external_field_mapping_detail: ExternalFieldMapping = Field(
        alias="externalFieldMappingDetail"
    )


class EntityField(BaseModel):
    """Model representing a field within an entity."""

    model_config = ConfigDict(
        validate_by_name=True,
    )
    id: Optional[str] = Field(default=None, alias="id")
    definition: Optional[FieldMetadata] = Field(default=None, alias="definition")


class ExternalObject(BaseModel):
    """Model representing an external object."""

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
    """Model representing external source fields."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )
    fields: List[ExternalField]
    external_object_detail: ExternalObject = Field(alias="externalObject")
    external_connection_detail: ExternalConnection = Field(alias="externalConnection")


class SourceJoinCriteria(BaseModel):
    """Model representing source join criteria."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        extra="allow",
    )
    id: Optional[str] = None
    entity_id: Optional[str] = Field(default=None, alias="entityId")
    join_field_name: Optional[str] = Field(default=None, alias="joinFieldName")
    join_type: Optional[str] = Field(default=None, alias="joinType")
    related_source_object_id: Optional[str] = Field(
        default=None, alias="relatedSourceObjectId"
    )
    related_source_object_field_name: Optional[str] = Field(
        default=None, alias="relatedSourceObjectFieldName"
    )
    related_source_field_name: Optional[str] = Field(
        default=None, alias="relatedSourceFieldName"
    )


class ChoiceSetValue(BaseModel):
    """Model representing a single value within a choice set."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )

    id: str = Field(alias="Id")
    name: str = Field(alias="Name")
    display_name: str = Field(alias="DisplayName")
    number_id: int = Field(alias="NumberId")
    created_time: str | None = Field(default=None, alias="CreateTime")
    updated_time: str | None = Field(default=None, alias="UpdateTime")
    created_by: str | None = Field(default=None, alias="CreatedBy")
    updated_by: str | None = Field(default=None, alias="UpdatedBy")
    record_owner: str | None = Field(default=None, alias="RecordOwner")


class EntityRecord(BaseModel):
    """Model representing a record within an entity."""

    model_config = {
        "validate_by_name": True,
        "validate_by_alias": True,
        "extra": "allow",
    }

    id: str = Field(alias="Id")

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
        pydantic_fields: dict[str, tuple[Any, EllipsisType | None]] = {}

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
                pydantic_fields[name] = (annotation, ...)

        # Dynamically create the Pydantic model class
        dynamic_model = create_model(
            f"Dynamic_{user_class.__name__}",
            **pydantic_fields,  # type: ignore[call-overload] # __base__ causes an issue. type checker cannot know that the key does not contain "__base__"
        )

        # Validate input data
        dynamic_model.model_validate(data)


class Entity(BaseModel):
    """Model representing an entity in the UiPath platform."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )

    name: str
    display_name: str = Field(alias="displayName")
    entity_type: str = Field(alias="entityType")
    description: Optional[str] = Field(default=None, alias="description")
    fields: Optional[List[FieldMetadata]] = Field(default=None, alias="fields")
    external_fields: Optional[
        List[ExternalField | ExternalSourceFields | Dict[str, Any]]
    ] = Field(
        default=None,
        alias="externalFields",
    )
    source_join_criteria: Optional[List[SourceJoinCriteria | Dict[str, Any]]] = Field(
        default=None,
        validation_alias=AliasChoices("sourceJoinCriteria", "sourceJoinCriterias"),
        alias="sourceJoinCriteria",
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


class FailureRecord(BaseModel):
    """A record that failed to insert/update/delete in a batch operation.

    Backend error responses for failed records do not always include a valid
    ``Id`` field — this model accepts arbitrary shapes so the caller can
    inspect ``error`` text and the original ``record`` payload.
    """

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
        extra="allow",
    )

    id: Optional[str] = Field(default=None, alias="Id")
    error: Optional[str] = Field(default=None)
    record: Optional[Dict[str, Any]] = Field(default=None)


class EntityRecordsBatchResponse(BaseModel):
    """Model representing a batch response of entity records."""

    model_config = ConfigDict(
        validate_by_name=True,
        validate_by_alias=True,
    )

    success_records: List[EntityRecord] = Field(
        default_factory=list, alias="successRecords"
    )
    failure_records: List[FailureRecord] = Field(
        default_factory=list, alias="failureRecords"
    )


class EntityRecordsListResponse(List[EntityRecord]):
    """List of EntityRecord with pagination metadata.

    Subclasses ``list`` so existing call sites that iterate, index, or call
    ``len()`` continue to work; new fields ``total_count``, ``has_next_page``,
    and ``next_cursor`` expose pagination information returned by the backend.
    """

    def __init__(
        self,
        items: Optional[List[EntityRecord]] = None,
        total_count: int = 0,
        has_next_page: bool = False,
        next_cursor: Optional[str] = None,
    ) -> None:
        """Construct from a list of records plus pagination metadata."""
        super().__init__(items or [])
        self.total_count = total_count
        self.has_next_page = has_next_page
        self.next_cursor = next_cursor


class LogicalOperator(IntEnum):
    """Logical operator for combining query filter groups."""

    And = 0
    Or = 1


class QueryFilterOperator(str, Enum):
    """Comparison operators supported by the structured query API."""

    Equals = "="
    NotEquals = "!="
    GreaterThan = ">"
    LessThan = "<"
    GreaterThanOrEqual = ">="
    LessThanOrEqual = "<="
    Contains = "contains"
    NotContains = "not contains"
    StartsWith = "startswith"
    EndsWith = "endswith"
    In = "in"
    NotIn = "not in"


class EntityQueryFilter(BaseModel):
    """A single filter condition for querying entity records.

    Backend operator/operand rules:

    * ``in`` / ``not in`` — require a non-empty ``value_list`` and reject
      ``value``.
    * ``=`` / ``!=`` — allow a null ``value`` (becomes ``IS NULL`` / ``IS
      NOT NULL``) and reject ``value_list``.
    * All other operators (``>``, ``<``, ``>=``, ``<=``, ``contains``,
      ``not contains``, ``startswith``, ``endswith``) — require a non-null
      ``value`` and reject ``value_list``.
    """

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    field_name: str = Field(alias="fieldName")
    operator: QueryFilterOperator
    value: Optional[str] = None
    value_list: Optional[List[str]] = Field(default=None, alias="valueList")

    @model_validator(mode="after")
    def _check_operator_operands(self) -> "EntityQueryFilter":
        """Reject operator/operand combinations the backend rejects.

        Implements the same rules the Data Service ``SelectQueryBuilder``
        enforces server-side, so callers see a clear local error instead of
        an opaque HTTP 400.
        """
        op = self.operator
        if op in (QueryFilterOperator.In, QueryFilterOperator.NotIn):
            if not self.value_list:
                raise ValueError(
                    f"Operator {op.value!r} requires a non-empty value_list."
                )
            if self.value is not None:
                raise ValueError(
                    f"Operator {op.value!r} uses value_list; value must be omitted."
                )
            return self

        if self.value_list is not None:
            raise ValueError(
                f"Operator {op.value!r} uses value; value_list must be omitted."
            )
        if (
            op not in (QueryFilterOperator.Equals, QueryFilterOperator.NotEquals)
            and self.value is None
        ):
            raise ValueError(f"Operator {op.value!r} requires a non-null value.")
        return self


class EntityQueryFilterGroup(BaseModel):
    """A group of query filters combined with a logical operator."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    logical_operator: Optional[LogicalOperator] = Field(
        default=None, alias="logicalOperator"
    )
    continue_logical_operator: Optional[LogicalOperator] = Field(
        default=None, alias="continueLogicalOperator"
    )
    query_filters: Optional[List[EntityQueryFilter]] = Field(
        default=None, alias="queryFilters"
    )
    filter_groups: Optional[List["EntityQueryFilterGroup"]] = Field(
        default=None, alias="filterGroups"
    )


class EntityQuerySortOption(BaseModel):
    """Sort option for query results."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    field_name: str = Field(alias="fieldName")
    is_descending: Optional[bool] = Field(default=None, alias="isDescending")


class EntityAggregateFunction(str, Enum):
    """Aggregate functions supported by the Data Fabric query API."""

    Count = "COUNT"
    Sum = "SUM"
    Avg = "AVG"
    Min = "MIN"
    Max = "MAX"


class EntityAggregate(BaseModel):
    """A single aggregate expression to apply during a query."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    function: EntityAggregateFunction
    field: str
    alias: Optional[str] = None


class EntityJoin(BaseModel):
    """Multi-entity JOIN definition for cross-entity queries."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    entity_name: Optional[str] = Field(default=None, alias="entityName")
    join_type: Optional[str] = Field(default=None, alias="joinType")
    join_field_name: Optional[str] = Field(default=None, alias="joinFieldName")
    related_entity_name: Optional[str] = Field(default=None, alias="relatedEntityName")
    related_field_name: Optional[str] = Field(default=None, alias="relatedFieldName")


class EntityBinning(BaseModel):
    """A binning (GROUP BY/aggregation) clause for V2 query endpoint."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    field_name: Optional[str] = Field(default=None, alias="fieldName")
    aggregate_function: Optional[EntityAggregateFunction] = Field(
        default=None, alias="aggregateFunction"
    )
    alias: Optional[str] = None


class AggregateRow(BaseModel):
    """A row returned by aggregate / group-by / binning queries.

    Aggregate rows do not have an ``Id`` field; columns vary by query
    (``selected_fields``, ``aggregates`` aliases, binning aliases) and are
    accessible as attributes via ``extra="allow"``.
    """

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )


class RetrieveEntityRecordsResponse(BaseModel):
    """Response from :meth:`EntitiesService.retrieve_records`.

    For plain queries, ``items`` is a list of :class:`EntityRecord`. When the
    query uses ``aggregates``, ``group_by``, or ``binnings``, the backend
    returns rows without an ``Id`` field; those rows are parsed as
    :class:`AggregateRow` instances.
    """

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    items: List[EntityRecord | AggregateRow] = Field(default_factory=list)
    total_count: int = Field(default=0, alias="totalCount")
    has_next_page: bool = Field(default=False, alias="hasNextPage")
    next_cursor: Optional[str] = Field(default=None, alias="nextCursor")

    def __iter__(self) -> Iterator[EntityRecord | AggregateRow]:  # type: ignore[override]
        """Iterate over records (delegates to ``self.items``)."""
        return iter(self.items)

    def __len__(self) -> int:
        """Return the number of records (delegates to ``self.items``)."""
        return len(self.items)

    @overload
    def __getitem__(self, index: int) -> EntityRecord | AggregateRow: ...

    @overload
    def __getitem__(self, index: slice) -> List[EntityRecord | AggregateRow]: ...

    def __getitem__(
        self, index: int | slice
    ) -> EntityRecord | AggregateRow | List[EntityRecord | AggregateRow]:
        """Index or slice records (delegates to ``self.items``)."""
        return self.items[index]


class EntityFieldDataType(str, Enum):
    """User-facing entity field data type names accepted by ``create_entity``."""

    UUID = "UUID"
    STRING = "STRING"
    INTEGER = "INTEGER"
    DATETIME = "DATETIME"
    DATETIME_WITH_TZ = "DATETIME_WITH_TZ"
    DECIMAL = "DECIMAL"
    FLOAT = "FLOAT"
    DOUBLE = "DOUBLE"
    DATE = "DATE"
    BOOLEAN = "BOOLEAN"
    BIG_INTEGER = "BIG_INTEGER"
    MULTILINE_TEXT = "MULTILINE_TEXT"
    FILE = "FILE"
    CHOICE_SET_SINGLE = "CHOICE_SET_SINGLE"
    CHOICE_SET_MULTIPLE = "CHOICE_SET_MULTIPLE"
    AUTO_NUMBER = "AUTO_NUMBER"
    RELATIONSHIP = "RELATIONSHIP"


# Maps the user-facing EntityFieldDataType to the ``(sqlType.name, fieldDisplayType)``
# tuple expected by the backend when creating an entity. ``sqlType.name`` is
# the raw SQL Server type the backend persists; ``fieldDisplayType`` controls
# how the field renders in the UI.
ENTITY_SCHEMA_FIELD_TYPE_MAP: Dict[EntityFieldDataType, "tuple[str, str]"] = {
    EntityFieldDataType.UUID: ("UNIQUEIDENTIFIER", "Basic"),
    EntityFieldDataType.STRING: ("NVARCHAR", "Basic"),
    EntityFieldDataType.INTEGER: ("INT", "Basic"),
    EntityFieldDataType.DATETIME: ("DATETIME2", "Basic"),
    EntityFieldDataType.DATETIME_WITH_TZ: ("DATETIMEOFFSET", "Basic"),
    EntityFieldDataType.DECIMAL: ("DECIMAL", "Basic"),
    EntityFieldDataType.FLOAT: ("FLOAT", "Basic"),
    EntityFieldDataType.DOUBLE: ("REAL", "Basic"),
    EntityFieldDataType.DATE: ("DATE", "Basic"),
    EntityFieldDataType.BOOLEAN: ("BIT", "Basic"),
    EntityFieldDataType.BIG_INTEGER: ("BIGINT", "Basic"),
    EntityFieldDataType.MULTILINE_TEXT: ("MULTILINE", "Basic"),
    EntityFieldDataType.FILE: ("UNIQUEIDENTIFIER", "File"),
    EntityFieldDataType.CHOICE_SET_SINGLE: ("INT", "ChoiceSetSingle"),
    EntityFieldDataType.CHOICE_SET_MULTIPLE: ("NVARCHAR", "ChoiceSetMultiple"),
    EntityFieldDataType.AUTO_NUMBER: ("DECIMAL", "AutoNumber"),
    EntityFieldDataType.RELATIONSHIP: ("UNIQUEIDENTIFIER", "Relationship"),
}

# Default and fixed sqlType constraint values applied when the caller does
# not supply them. The backend requires these on field creation — without
# them the field is stored in an incomplete state and the UI later fails
# with "Field type cannot be changed" when editing advanced options.
ENTITY_FIELD_CONSTRAINT_DEFAULTS: Dict[str, int] = {
    "STRING_LENGTH_LIMIT": 200,
    "MULTILINE_TEXT_LENGTH_LIMIT": 200,
    "DECIMAL_LENGTH_LIMIT": 1000,
    "DECIMAL_PRECISION": 2,
    "BOOLEAN_LENGTH_LIMIT": 100,
    "DATE_LENGTH_LIMIT": 1000,
    "UNIQUEIDENTIFIER_LENGTH_LIMIT": 300,
    "CHOICE_SET_MULTIPLE_LENGTH_LIMIT": 4000,
    "NUMERIC_MAX_VALUE": 1_000_000_000_000,
    "NUMERIC_MIN_VALUE": -1_000_000_000_000,
}

# Per-field-type spec describing which user-supplied constraints are valid
# and their inclusive ranges. Field types absent from this map (BOOLEAN,
# DATE, DATETIME, DATETIME_WITH_TZ, FILE, RELATIONSHIP, UUID, CHOICE_SET_*,
# AUTO_NUMBER) accept no user-supplied constraints — passing one raises
# ``ValueError`` so the caller gets a clear local error before any HTTP call.
_MAX_SAFE_INTEGER = 9_007_199_254_740_991

ENTITY_FIELD_CONSTRAINT_SPEC: Dict[
    EntityFieldDataType, Dict[str, "tuple[int, int]"]
] = {
    EntityFieldDataType.STRING: {
        "length_limit": (1, 4000),
    },
    EntityFieldDataType.MULTILINE_TEXT: {
        "length_limit": (1, 10000),
    },
    EntityFieldDataType.INTEGER: {
        "max_value": (-_MAX_SAFE_INTEGER, _MAX_SAFE_INTEGER),
        "min_value": (-_MAX_SAFE_INTEGER, _MAX_SAFE_INTEGER),
    },
    EntityFieldDataType.BIG_INTEGER: {
        "max_value": (-_MAX_SAFE_INTEGER, _MAX_SAFE_INTEGER),
        "min_value": (-_MAX_SAFE_INTEGER, _MAX_SAFE_INTEGER),
    },
    EntityFieldDataType.DECIMAL: {
        "max_value": (-_MAX_SAFE_INTEGER, _MAX_SAFE_INTEGER),
        "min_value": (-_MAX_SAFE_INTEGER, _MAX_SAFE_INTEGER),
        "decimal_precision": (0, 10),
    },
    EntityFieldDataType.FLOAT: {
        "max_value": (-_MAX_SAFE_INTEGER, _MAX_SAFE_INTEGER),
        "min_value": (-_MAX_SAFE_INTEGER, _MAX_SAFE_INTEGER),
        "decimal_precision": (0, 10),
    },
    EntityFieldDataType.DOUBLE: {
        "max_value": (-_MAX_SAFE_INTEGER, _MAX_SAFE_INTEGER),
        "min_value": (-_MAX_SAFE_INTEGER, _MAX_SAFE_INTEGER),
        "decimal_precision": (0, 10),
    },
}

RESERVED_FIELD_NAMES = frozenset(
    ["Id", "CreatedBy", "CreateTime", "UpdatedBy", "UpdateTime"]
)
"""Field names reserved by the backend — using one as a user field name is rejected."""


class EntityCreateFieldOptions(BaseModel):
    """User-facing field definition for creating or updating entity schemas."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    field_name: str = Field(alias="fieldName")
    type: Optional[EntityFieldDataType] = Field(
        default=EntityFieldDataType.STRING, alias="type"
    )
    display_name: Optional[str] = Field(default=None, alias="displayName")
    description: Optional[str] = None
    is_required: Optional[bool] = Field(default=None, alias="isRequired")
    is_unique: Optional[bool] = Field(default=None, alias="isUnique")
    is_rbac_enabled: Optional[bool] = Field(default=None, alias="isRbacEnabled")
    is_encrypted: Optional[bool] = Field(default=None, alias="isEncrypted")
    default_value: Optional[str] = Field(default=None, alias="defaultValue")
    length_limit: Optional[int] = Field(default=None, alias="lengthLimit")
    max_value: Optional[int] = Field(default=None, alias="maxValue")
    min_value: Optional[int] = Field(default=None, alias="minValue")
    decimal_precision: Optional[int] = Field(default=None, alias="decimalPrecision")
    choice_set_id: Optional[str] = Field(default=None, alias="choiceSetId")
    reference_entity_name: Optional[str] = Field(
        default=None, alias="referenceEntityName"
    )
    reference_field_name: Optional[str] = Field(
        default=None, alias="referenceFieldName"
    )


class EntityCreateOptions(BaseModel):
    """Options for creating a new Data Fabric entity."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    display_name: Optional[str] = Field(default=None, alias="displayName")
    description: Optional[str] = None
    folder_key: Optional[str] = Field(default=None, alias="folderKey")
    is_rbac_enabled: Optional[bool] = Field(default=None, alias="isRbacEnabled")
    is_analytics_enabled: Optional[bool] = Field(
        default=None, alias="isAnalyticsEnabled"
    )
    external_fields: Optional[List[Dict[str, Any]]] = Field(
        default=None, alias="externalFields"
    )


class EntityMetadataUpdateOptions(BaseModel):
    """Options for updating an entity's metadata via PATCH /metadata."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    display_name: Optional[str] = Field(default=None, alias="displayName")
    description: Optional[str] = None
    is_rbac_enabled: Optional[bool] = Field(default=None, alias="isRbacEnabled")


class EntityImportRecordsResponse(BaseModel):
    """Response from a bulk import operation."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    total_records: int = Field(default=0, alias="totalRecords")
    inserted_records: int = Field(default=0, alias="insertedRecords")
    error_file_link: Optional[str] = Field(default=None, alias="errorFileLink")


class EntityRouting(BaseModel):
    """A single entity-to-folder routing entry for query execution."""

    model_config = ConfigDict(populate_by_name=True)

    entity_name: str = Field(alias="entityName")
    folder_id: str = Field(alias="folderId")
    override_entity_name: Optional[str] = Field(
        default=None, alias="overrideEntityName"
    )


class QueryRoutingOverrideContext(BaseModel):
    """Routing context that maps entities to their folders for multi-entity queries."""

    model_config = ConfigDict(populate_by_name=True)

    entity_routings: List[EntityRouting] = Field(alias="entityRoutings")


class DataFabricEntityItem(BaseModel):
    """A single Data Fabric entity reference from agent configuration."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    id: str
    entity_key: Optional[str] = Field(None, alias="referenceKey")
    name: str
    folder_key: str = Field(alias="folderId")
    description: Optional[str] = None


class EntitySetResolution(BaseModel):
    """Result of resolving an agent entity set with overwrites applied."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    entities: list[Entity]
    entities_service: EntitiesService


Entity.model_rebuild()
EntityQueryFilterGroup.model_rebuild()
