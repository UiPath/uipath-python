"""Response models for the v3 Data Fabric entities API (preview).

The v3 API returns a different wire shape than v1/v2. Record reads and writes
return an :class:`EntityWriteResponseV3` *envelope* whose root-entity field
values are flattened onto the top-level JSON object alongside the reserved
envelope keys (``Id``, ``children``, ``cascadeDeletedChildren``,
``deletedCount``, ``updatedCount``). These models mirror the backend
``StorageManager/Models`` and ``Common/Model`` types and are returned by
:class:`~uipath.platform.entities._entities_service_v3.EntitiesServiceV3`.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional, overload

from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from .entities import Entity

# Reserved top-level keys on a v3 write/query envelope. Every other top-level
# key is a flattened root-entity field folded into ``root_fields``.
_ENVELOPE_KEYS = frozenset(
    {
        "Id",
        "id",
        "children",
        "cascadeDeletedChildren",
        "deletedCount",
        "updatedCount",
    }
)


class ChildArrayPaginationRef(BaseModel):
    """Pagination pointer for a composite child array that has more records."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    query_url: Optional[str] = Field(default=None, alias="queryUrl")
    query_request: Optional[Dict[str, Any]] = Field(default=None, alias="queryRequest")


class ChildArrayBlock(BaseModel):
    """A page of child-member records nested under a composite parent record."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    records: List[Dict[str, Any]] = Field(default_factory=list, alias="records")
    has_more: bool = Field(default=False, alias="hasMore")
    ref: Optional[ChildArrayPaginationRef] = Field(default=None, alias="ref")


class EntityWriteResponseV3(BaseModel):
    """A single v3 record envelope returned by reads, writes, and queries.

    Root-entity field values live in :attr:`root_fields`; the backend flattens
    them onto the top-level JSON object, so on parse any top-level key that is
    not a reserved envelope key is folded into ``root_fields``. Serialization
    reproduces that flattening. ``children`` and the ``*_count`` fields carry
    composite/write metadata and are empty/zero for plain single-entity records.
    """

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    id: Optional[str] = Field(default=None, alias="Id")
    children: Dict[str, ChildArrayBlock] = Field(default_factory=dict, alias="children")
    cascade_deleted_children: Dict[str, int] = Field(
        default_factory=dict, alias="cascadeDeletedChildren"
    )
    deleted_count: int = Field(default=0, alias="deletedCount")
    updated_count: int = Field(default=0, alias="updatedCount")
    root_fields: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _fold_root_fields(cls, data: Any) -> Any:
        """Fold flattened top-level tenant fields into ``root_fields``."""
        if not isinstance(data, dict):
            return data
        root: Dict[str, Any] = dict(
            data.get("root_fields") or data.get("rootFields") or {}
        )
        normalized: Dict[str, Any] = {}
        for key, value in data.items():
            if key in ("root_fields", "rootFields"):
                continue
            if key in _ENVELOPE_KEYS:
                normalized[key] = value
            else:
                root[key] = value
        normalized["root_fields"] = root
        return normalized

    @model_serializer(mode="plain")
    def _serialize(self) -> Dict[str, Any]:
        """Reproduce the flattened wire shape (root fields at the top level)."""
        out: Dict[str, Any] = {}
        if self.id is not None:
            out["Id"] = self.id
        out.update(self.root_fields)
        out["children"] = {
            name: block.model_dump(by_alias=True)
            for name, block in self.children.items()
        }
        out["cascadeDeletedChildren"] = dict(self.cascade_deleted_children)
        out["deletedCount"] = self.deleted_count
        # The backend omits updatedCount when zero; mirror that.
        if self.updated_count:
            out["updatedCount"] = self.updated_count
        return out

    def __getitem__(self, key: str) -> Any:
        """Access a flattened root-entity field by name."""
        return self.root_fields[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Return a flattened root-entity field, or ``default`` if absent."""
        return self.root_fields.get(key, default)


class QueryResponseV3(BaseModel):
    """Result of a v3 structured query.

    ``value`` is a list of :class:`EntityWriteResponseV3` envelopes.
    ``total_record_count_is_estimate`` is ``True`` only when the backend used a
    bounded-fetch fallback and the count is approximate.
    """

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    value: List[EntityWriteResponseV3] = Field(default_factory=list, alias="value")
    total_record_count: int = Field(default=0, alias="totalRecordCount")
    total_record_count_is_estimate: bool = Field(
        default=False, alias="totalRecordCountIsEstimate"
    )

    def __iter__(self) -> Iterator[EntityWriteResponseV3]:  # type: ignore[override]
        """Iterate over the record envelopes (delegates to ``self.value``)."""
        return iter(self.value)

    def __len__(self) -> int:
        """Return the number of records (delegates to ``self.value``)."""
        return len(self.value)

    @overload
    def __getitem__(self, index: int) -> EntityWriteResponseV3: ...

    @overload
    def __getitem__(self, index: slice) -> List[EntityWriteResponseV3]: ...

    def __getitem__(
        self, index: int | slice
    ) -> EntityWriteResponseV3 | List[EntityWriteResponseV3]:
        """Index or slice the record envelopes (delegates to ``self.value``)."""
        return self.value[index]


class BatchOperationFailureRecord(BaseModel):
    """A single record that failed within a v3 batch operation."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    error: Optional[str] = Field(default=None, alias="error")
    record: Optional[Dict[str, Any]] = Field(default=None, alias="record")


class BatchOperationResponse(BaseModel):
    """Result of a v3 batch insert/update/delete.

    ``success_records`` are flat field-value dicts (not envelopes);
    ``failure_records`` carry the per-record error plus the original payload.
    """

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    success_records: List[Dict[str, Any]] = Field(
        default_factory=list, alias="successRecords"
    )
    failure_records: List[BatchOperationFailureRecord] = Field(
        default_factory=list, alias="failureRecords"
    )


class EntityRecordV3(Entity):
    """A v3 entity *definition* (schema), extending :class:`Entity`.

    Adds ``entity_class`` (``Native`` / ``Federated`` / ``Case``), a computed
    classification the v3 schema endpoints return.
    """

    entity_class: Optional[str] = Field(default=None, alias="entityClass")


class CompositeMemberMetadata(BaseModel):
    """Metadata for a single member of a composite entity."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    entity_id: str = Field(alias="entityId")
    entity_name: str = Field(alias="entityName")
    display_name: Optional[str] = Field(default=None, alias="displayName")
    is_root: bool = Field(default=False, alias="isRoot")
    parent_entity_name: Optional[str] = Field(default=None, alias="parentEntityName")
    foreign_key_field_name: Optional[str] = Field(
        default=None, alias="foreignKeyFieldName"
    )
    parent_target_field_name: Optional[str] = Field(
        default=None, alias="parentTargetFieldName"
    )


class CompositeInfo(BaseModel):
    """Structure of a composite entity: its root and member entities."""

    model_config = ConfigDict(
        validate_by_name=True, validate_by_alias=True, extra="allow"
    )

    entity_id: str = Field(alias="entityId")
    root_entity_name: Optional[str] = Field(default=None, alias="rootEntityName")
    members: List[CompositeMemberMetadata] = Field(
        default_factory=list, alias="members"
    )


class CompositeEntityMetadataResponse(EntityRecordV3):
    """v3 entity metadata; extends :class:`EntityRecordV3` with composite info."""

    is_composite: bool = Field(default=False, alias="isComposite")
    composite_info: Optional[CompositeInfo] = Field(default=None, alias="compositeInfo")


class GetAllResponseV3(BaseModel):
    """Full v3 schema catalog: all entities plus all choice sets in one call."""

    model_config = ConfigDict(validate_by_name=True, validate_by_alias=True)

    entities: List[EntityRecordV3] = Field(default_factory=list, alias="entities")
    choicesets: List[Dict[str, Any]] = Field(default_factory=list, alias="choicesets")
