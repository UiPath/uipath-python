"""Schema-side operations for the Data Fabric entities surface.

Handles entity definitions, choice set listings, and the create / delete /
update-metadata lifecycle that targets the backend ``EntityController``.
Record CRUD, queries, attachments, and bulk import live on
:class:`EntityDataService` and are mediated by :class:`EntitiesService`.
"""

import re
from typing import Any, Dict, List, Optional, Sequence

from httpx import Response

from uipath.platform.constants import HEADER_FOLDER_KEY

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._models import Endpoint, RequestSpec
from ..orchestrator._folder_service import FolderService
from .entities import (
    ENTITY_CLASS_TO_ID_MAP,
    ENTITY_FIELD_CONSTRAINT_DEFAULTS,
    ENTITY_FIELD_CONSTRAINT_SPEC,
    ENTITY_SCHEMA_FIELD_TYPE_MAP,
    RESERVED_FIELD_NAMES,
    Entity,
    EntityClass,
    EntityCreateExternalField,
    EntityCreateExternalSource,
    EntityCreateFieldOptions,
    EntityCreateOptions,
    EntityFieldDataType,
    EntityMetadataUpdateOptions,
)

DATA_FABRIC_TENANT_FOLDER_ID = "00000000-0000-0000-0000-000000000000"

_V1_ENTITIES = "datafabric_/api/Entity"
_V3_ENTITIES = "datafabric_/api/v3/entities"


def _schema_base(use_v3: bool) -> str:
    """Return the entity-schema endpoint root for the requested API version."""
    return _V3_ENTITIES if use_v3 else _V1_ENTITIES


_NAME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9]*$")
"""Entity and field name pattern: must start with a letter, then letters and digits only.

Matches the UI's create-entity / create-field form validators so any name accepted
here can later be displayed or edited through the Data Service UI.
"""

_ENTITY_NAME_MIN_LENGTH = 1
_ENTITY_NAME_MAX_LENGTH = 30
_FIELD_NAME_MIN_LENGTH = 3
_FIELD_NAME_MAX_LENGTH = 100


class EntitySchemaService(BaseService):
    """HTTP service for entity-schema operations.

    Provides retrieval and lifecycle management for entities and choice sets.
    Each operation targets either the legacy v1 ``datafabric_/api/Entity``
    surface or the ``datafabric_/api/v3/entities`` surface depending on
    ``use_v3``; only v3 serves Federated entities. Choice-set listing is v1 only.

    See Also:
        https://docs.uipath.com/data-service/automation-cloud/latest/user-guide/introduction

    !!! warning "Preview Feature"
        This service is currently experimental. Behavior and parameters are
        subject to change in future versions.
    """

    def __init__(
        self,
        config: UiPathApiConfig,
        execution_context: UiPathExecutionContext,
        folders_service: Optional[FolderService] = None,
    ) -> None:
        """Initialise the schema service."""
        super().__init__(config=config, execution_context=execution_context)
        self._folders_service = folders_service

    def retrieve(self, entity_key: str, use_v3: bool = False) -> Entity:
        """Internal implementation; see :meth:`EntitiesService.retrieve`."""
        spec = self._retrieve_spec(entity_key, use_v3=use_v3)
        response = self.request(spec.method, spec.endpoint)
        return Entity.model_validate(response.json())

    async def retrieve_async(self, entity_key: str, use_v3: bool = False) -> Entity:
        """Async variant of :meth:`retrieve`."""
        spec = self._retrieve_spec(entity_key, use_v3=use_v3)
        response = await self.request_async(spec.method, spec.endpoint)
        return Entity.model_validate(response.json())

    def retrieve_by_name(
        self,
        entity_name: str,
        folder_key: Optional[str] = None,
        use_v3: bool = False,
    ) -> Entity:
        """Internal implementation; see :meth:`EntitiesService.retrieve_by_name`."""
        spec = self._retrieve_by_name_spec(entity_name, use_v3=use_v3)
        headers = self._folder_key_headers(folder_key)
        response = self.request(spec.method, spec.endpoint, headers=headers)
        return Entity.model_validate(response.json())

    async def retrieve_by_name_async(
        self,
        entity_name: str,
        folder_key: Optional[str] = None,
        use_v3: bool = False,
    ) -> Entity:
        """Async variant of :meth:`retrieve_by_name`."""
        spec = self._retrieve_by_name_spec(entity_name, use_v3=use_v3)
        headers = self._folder_key_headers(folder_key)
        response = await self.request_async(spec.method, spec.endpoint, headers=headers)
        return Entity.model_validate(response.json())

    def list_entities(self, use_v3: bool = False) -> List[Entity]:
        """Internal implementation; see :meth:`EntitiesService.list_entities`."""
        spec = self._list_entities_spec(use_v3=use_v3)
        response = self.request(spec.method, spec.endpoint)
        entities_data = response.json()
        return [Entity.model_validate(entity) for entity in entities_data]

    async def list_entities_async(self, use_v3: bool = False) -> List[Entity]:
        """Async variant of :meth:`list_entities`."""
        spec = self._list_entities_spec(use_v3=use_v3)
        response = await self.request_async(spec.method, spec.endpoint)
        entities_data = response.json()
        return [Entity.model_validate(entity) for entity in entities_data]

    def list_choicesets(self) -> List[Entity]:
        """Internal implementation; see :meth:`EntitiesService.list_choicesets`."""
        spec = self._list_choicesets_spec()
        response = self.request(spec.method, spec.endpoint)
        return [Entity.model_validate(item) for item in response.json()]

    async def list_choicesets_async(self) -> List[Entity]:
        """Async variant of :meth:`list_choicesets`."""
        spec = self._list_choicesets_spec()
        response = await self.request_async(spec.method, spec.endpoint)
        return [Entity.model_validate(item) for item in response.json()]

    def create_entity(
        self,
        name: str,
        fields: List[EntityCreateFieldOptions],
        options: Optional[EntityCreateOptions] = None,
        use_v3: bool = False,
    ) -> str:
        """Internal implementation; see :meth:`EntitiesService.create_entity`."""
        spec = self._create_entity_spec(name, fields, options, use_v3=use_v3)
        response = self.request(spec.method, spec.endpoint, json=spec.json)
        return self._extract_entity_id(response)

    async def create_entity_async(
        self,
        name: str,
        fields: List[EntityCreateFieldOptions],
        options: Optional[EntityCreateOptions] = None,
        use_v3: bool = False,
    ) -> str:
        """Async variant of :meth:`create_entity`."""
        spec = self._create_entity_spec(name, fields, options, use_v3=use_v3)
        response = await self.request_async(spec.method, spec.endpoint, json=spec.json)
        return self._extract_entity_id(response)

    def delete_entity(self, entity_id: str, use_v3: bool = False) -> None:
        """Delete an entity and all of its records."""
        spec = self._delete_entity_spec(entity_id, use_v3=use_v3)
        self.request(spec.method, spec.endpoint)

    async def delete_entity_async(self, entity_id: str, use_v3: bool = False) -> None:
        """Async variant of :meth:`delete_entity`."""
        spec = self._delete_entity_spec(entity_id, use_v3=use_v3)
        await self.request_async(spec.method, spec.endpoint)

    def update_entity_metadata(
        self,
        entity_id: str,
        metadata: EntityMetadataUpdateOptions | Dict[str, Any],
        use_v3: bool = False,
    ) -> None:
        """Internal implementation; see :meth:`EntitiesService.update_entity_metadata`."""
        spec = self._update_entity_metadata_spec(entity_id, metadata, use_v3=use_v3)
        self.request(spec.method, spec.endpoint, json=spec.json)

    async def update_entity_metadata_async(
        self,
        entity_id: str,
        metadata: EntityMetadataUpdateOptions | Dict[str, Any],
        use_v3: bool = False,
    ) -> None:
        """Async variant of :meth:`update_entity_metadata`."""
        spec = self._update_entity_metadata_spec(entity_id, metadata, use_v3=use_v3)
        await self.request_async(spec.method, spec.endpoint, json=spec.json)

    # ------------------------------------------------------------------
    # Request-spec builders
    # ------------------------------------------------------------------

    @staticmethod
    def _retrieve_spec(entity_key: str, use_v3: bool = False) -> RequestSpec:
        """Build the GET spec for fetching an entity by key."""
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"{_schema_base(use_v3)}/{entity_key}"),
        )

    @staticmethod
    def _retrieve_by_name_spec(entity_name: str, use_v3: bool = False) -> RequestSpec:
        """Build the GET spec for fetching an entity by name."""
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"{_schema_base(use_v3)}/{entity_name}/metadata"),
        )

    @staticmethod
    def _folder_key_headers(folder_key: Optional[str]) -> Dict[str, str]:
        """Return the folder-key header dict, empty when no key is supplied."""
        if folder_key:
            return {HEADER_FOLDER_KEY: folder_key}
        return {}

    @staticmethod
    def _list_entities_spec(use_v3: bool = False) -> RequestSpec:
        """Build the GET spec for listing all entities (non-choice-sets)."""
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(_schema_base(use_v3)),
        )

    @staticmethod
    def _list_choicesets_spec() -> RequestSpec:
        """Build the GET spec for listing all choice sets."""
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("datafabric_/api/Entity/choiceset"),
        )

    @classmethod
    def _create_entity_spec(
        cls,
        name: str,
        fields: List[EntityCreateFieldOptions],
        options: Optional[EntityCreateOptions] = None,
        use_v3: bool = False,
    ) -> RequestSpec:
        """Build the POST spec for creating an entity with its field schema.

        On v3, a federated entity is created by passing
        ``options.entity_class = EntityClass.Federated`` with at least one
        source in ``options.external_fields`` and any cross-source joins in
        ``options.source_join_condition_details``. The legacy v1 endpoint does
        not support Federated entities.
        """
        cls._validate_name(name, "entity")
        for field in fields:
            cls._validate_name(field.field_name, "field")
        opts = options or EntityCreateOptions()

        if not use_v3:
            return cls._create_entity_spec_v1(name, fields, opts)

        entity_class_id: Optional[int] = None
        if opts.entity_class is not None:
            if opts.entity_class not in (EntityClass.Native, EntityClass.Federated):
                raise ValueError(
                    f"entityClass {opts.entity_class.value!r} is not creatable. "
                    "Use EntityClass.Native or EntityClass.Federated."
                )
            entity_class_id = int(ENTITY_CLASS_TO_ID_MAP[opts.entity_class])
        if opts.entity_class is EntityClass.Federated and not opts.external_fields:
            raise ValueError(
                "Federated entities require at least one external source in "
                "external_fields."
            )

        entity_definition: Dict[str, Any] = {
            "name": name,
            "fields": [cls._build_schema_field_payload(f) for f in fields],
            "folderId": opts.folder_key or DATA_FABRIC_TENANT_FOLDER_ID,
            "isRbacEnabled": bool(opts.is_rbac_enabled or False),
            "isInsightsEnabled": bool(opts.is_analytics_enabled or False),
            "externalFields": cls._build_external_sources_payload(opts.external_fields),
        }
        if entity_class_id is not None:
            entity_definition["entityClassId"] = entity_class_id
        if opts.source_join_condition_details is not None:
            entity_definition["sourceJoinConditionDetails"] = [
                j.model_dump(by_alias=True, exclude_none=True, mode="json")
                for j in opts.source_join_condition_details
            ]

        payload: Dict[str, Any] = {
            "displayName": opts.display_name or name,
            "entityDefinition": entity_definition,
        }
        if opts.description is not None:
            payload["description"] = opts.description
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(_V3_ENTITIES),
            json=payload,
        )

    @classmethod
    def _create_entity_spec_v1(
        cls,
        name: str,
        fields: List[EntityCreateFieldOptions],
        opts: EntityCreateOptions,
    ) -> RequestSpec:
        """Build the legacy v1 create-entity POST spec (no Federated support).

        The user-facing option ``is_analytics_enabled`` maps to the legacy
        backend field name ``isInsightsEnabled`` — the wire name predates the
        "Analytics" UI rename.
        """
        external_fields = [
            source.model_dump(by_alias=True, exclude_none=True, mode="json")
            if isinstance(source, EntityCreateExternalSource)
            else source
            for source in (opts.external_fields or [])
        ]
        payload: Dict[str, Any] = {
            "displayName": opts.display_name or name,
            "entityDefinition": {
                "name": name,
                "fields": [cls._build_schema_field_payload(f) for f in fields],
                "folderId": opts.folder_key or DATA_FABRIC_TENANT_FOLDER_ID,
                "isRbacEnabled": bool(opts.is_rbac_enabled or False),
                "isInsightsEnabled": bool(opts.is_analytics_enabled or False),
                "externalFields": external_fields,
            },
        }
        if opts.description is not None:
            payload["description"] = opts.description
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(_V1_ENTITIES),
            json=payload,
        )

    @classmethod
    def _build_external_sources_payload(
        cls,
        sources: Optional[Sequence[EntityCreateExternalSource | Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Build the wire ``externalFields`` payload for a federated entity.

        Each source's internal columns run through the same field pipeline as
        native fields (so ``fieldDefinition`` is identical to a native field),
        paired with its external mapping and source connection/object details.
        Dict inputs are validated through :class:`EntityCreateExternalSource`.
        """
        if not sources:
            return []
        built: List[Dict[str, Any]] = []
        for source in sources:
            if not isinstance(source, EntityCreateExternalSource):
                source = EntityCreateExternalSource.model_validate(source)
            entry: Dict[str, Any] = {
                "fields": cls._build_external_fields_payload(source.fields),
                "externalObjectDetail": source.external_object_detail.model_dump(
                    by_alias=True, exclude_none=True, mode="json"
                ),
            }
            if source.external_connection_detail is not None:
                entry["externalConnectionDetail"] = (
                    source.external_connection_detail.model_dump(
                        by_alias=True, exclude_none=True, mode="json"
                    )
                )
            if source.native_connection_detail is not None:
                entry["nativeConnectionDetail"] = (
                    source.native_connection_detail.model_dump(
                        by_alias=True, exclude_none=True, mode="json"
                    )
                )
            built.append(entry)
        return built

    @classmethod
    def _build_external_fields_payload(
        cls,
        fields: Optional[List[EntityCreateExternalField]],
    ) -> List[Dict[str, Any]]:
        """Build the wire ``fields`` payload for a federated source.

        Produces ``{fieldDefinition, externalFieldMappingDetail}`` per field —
        ``fieldDefinition`` is the native field payload, ``externalFieldMappingDetail``
        the source mapping (``directionType`` numeric, per :class:`DataDirectionType`).
        """
        if not fields:
            return []
        return [
            {
                "fieldDefinition": cls._build_schema_field_payload(f.field),
                "externalFieldMappingDetail": f.external_field_mapping_detail.model_dump(
                    by_alias=True, exclude_none=True, mode="json"
                ),
            }
            for f in fields
        ]

    @staticmethod
    def _delete_entity_spec(entity_id: str, use_v3: bool = False) -> RequestSpec:
        """Build the DELETE spec for removing an entity."""
        return RequestSpec(
            method="DELETE",
            endpoint=Endpoint(f"{_schema_base(use_v3)}/{entity_id}"),
        )

    @staticmethod
    def _update_entity_metadata_spec(
        entity_id: str,
        metadata: EntityMetadataUpdateOptions | Dict[str, Any],
        use_v3: bool = False,
    ) -> RequestSpec:
        """Build the PATCH spec for updating entity metadata.

        Dict inputs are validated through :class:`EntityMetadataUpdateOptions`
        so snake_case keys (``display_name``) and camelCase keys
        (``displayName``) both serialise to the API field names the backend
        expects.
        """
        if not isinstance(metadata, EntityMetadataUpdateOptions):
            metadata = EntityMetadataUpdateOptions.model_validate(metadata)
        body = metadata.model_dump(by_alias=True, exclude_none=True)
        return RequestSpec(
            method="PATCH",
            endpoint=Endpoint(f"{_schema_base(use_v3)}/{entity_id}/metadata"),
            json=body,
        )

    @classmethod
    def _build_schema_field_payload(
        cls, field: EntityCreateFieldOptions
    ) -> Dict[str, Any]:
        """Build the API field payload for a single field on create-entity.

        Maps :class:`EntityFieldDataType` to the backend's ``sqlType.name`` and
        ``fieldDisplayType`` (e.g. ``STRING`` becomes ``NVARCHAR`` / ``Basic``).
        Caller-supplied constraints are validated against
        :data:`ENTITY_FIELD_CONSTRAINT_SPEC`; unsupplied per-type constraints
        fall back to :data:`ENTITY_FIELD_CONSTRAINT_DEFAULTS` so the field is
        persisted fully and remains editable later.
        """
        ftype = field.type or EntityFieldDataType.STRING
        cls._validate_name(field.field_name, "field")
        cls._validate_field_constraints(ftype, field)

        sql_type_name, field_display_type = ENTITY_SCHEMA_FIELD_TYPE_MAP[ftype]
        sql_type: Dict[str, Any] = {"name": sql_type_name}
        sql_type.update(cls._build_sql_type_constraints(ftype, field))

        payload: Dict[str, Any] = {
            "name": field.field_name,
            "displayName": field.display_name or field.field_name,
            "sqlType": sql_type,
            "fieldDisplayType": field_display_type,
            "description": field.description or "",
            "isRequired": bool(field.is_required or False),
            "isUnique": bool(field.is_unique or False),
            "isRbacEnabled": bool(field.is_rbac_enabled or False),
            "isEncrypted": bool(field.is_encrypted or False),
        }
        if field.default_value is not None:
            payload["defaultValue"] = field.default_value
        if field.choice_set_id is not None:
            payload["choiceSetId"] = field.choice_set_id
        if field.reference_entity_name is not None:
            payload["referenceEntityName"] = field.reference_entity_name
        if field.reference_field_name is not None:
            payload["referenceFieldName"] = field.reference_field_name
        return payload

    @staticmethod
    def _build_sql_type_constraints(
        ftype: EntityFieldDataType, field: EntityCreateFieldOptions
    ) -> Dict[str, Any]:
        """Return the ``sqlType`` constraint fields required for ``ftype``.

        Caller-supplied values override defaults where the type accepts them;
        types that take no constraints (UUID, DATETIME, CHOICE_SET_SINGLE,
        AUTO_NUMBER) return an empty dict.
        """
        d = ENTITY_FIELD_CONSTRAINT_DEFAULTS
        if ftype is EntityFieldDataType.STRING:
            return {"lengthLimit": field.length_limit or d["STRING_LENGTH_LIMIT"]}
        if ftype is EntityFieldDataType.MULTILINE_TEXT:
            return {
                "lengthLimit": field.length_limit or d["MULTILINE_TEXT_LENGTH_LIMIT"]
            }
        if ftype is EntityFieldDataType.DECIMAL:
            return {
                "lengthLimit": d["DECIMAL_LENGTH_LIMIT"],
                "decimalPrecision": (
                    field.decimal_precision
                    if field.decimal_precision is not None
                    else d["DECIMAL_PRECISION"]
                ),
                "maxValue": (
                    field.max_value
                    if field.max_value is not None
                    else d["NUMERIC_MAX_VALUE"]
                ),
                "minValue": (
                    field.min_value
                    if field.min_value is not None
                    else d["NUMERIC_MIN_VALUE"]
                ),
            }
        if ftype is EntityFieldDataType.BOOLEAN:
            return {"lengthLimit": d["BOOLEAN_LENGTH_LIMIT"]}
        if ftype in (
            EntityFieldDataType.DATE,
            EntityFieldDataType.DATETIME_WITH_TZ,
        ):
            return {"lengthLimit": d["DATE_LENGTH_LIMIT"]}
        if ftype in (EntityFieldDataType.INTEGER, EntityFieldDataType.BIG_INTEGER):
            return {
                "maxValue": (
                    field.max_value
                    if field.max_value is not None
                    else d["NUMERIC_MAX_VALUE"]
                ),
                "minValue": (
                    field.min_value
                    if field.min_value is not None
                    else d["NUMERIC_MIN_VALUE"]
                ),
            }
        if ftype in (EntityFieldDataType.FLOAT, EntityFieldDataType.DOUBLE):
            return {
                "decimalPrecision": (
                    field.decimal_precision
                    if field.decimal_precision is not None
                    else d["DECIMAL_PRECISION"]
                ),
                "maxValue": (
                    field.max_value
                    if field.max_value is not None
                    else d["NUMERIC_MAX_VALUE"]
                ),
                "minValue": (
                    field.min_value
                    if field.min_value is not None
                    else d["NUMERIC_MIN_VALUE"]
                ),
            }
        if ftype in (EntityFieldDataType.FILE, EntityFieldDataType.RELATIONSHIP):
            return {"lengthLimit": d["UNIQUEIDENTIFIER_LENGTH_LIMIT"]}
        if ftype is EntityFieldDataType.CHOICE_SET_MULTIPLE:
            return {"lengthLimit": d["CHOICE_SET_MULTIPLE_LENGTH_LIMIT"]}
        # UUID, DATETIME, CHOICE_SET_SINGLE, AUTO_NUMBER — no constraints
        return {}

    @staticmethod
    def _validate_name(name: str, context: str) -> None:
        r"""Validate an entity or field name against the UI's create-form rules.

        Entity names must be 1-30 characters; field names must be 3-100
        characters. Both must match ``^[a-zA-Z][a-zA-Z0-9]*$`` — start with a
        letter, then letters or digits only (underscores are not permitted, to
        stay consistent with the UI's entity / field creation forms).

        Field names additionally cannot collide with the system-reserved field
        names in :data:`RESERVED_FIELD_NAMES`; the reserved-name check runs
        first so that short reserved names produce a more informative error.
        """
        if context == "field":
            if name in RESERVED_FIELD_NAMES:
                reserved = ", ".join(sorted(RESERVED_FIELD_NAMES))
                raise ValueError(
                    f"Field name {name!r} is reserved. Reserved names: {reserved}."
                )
            min_len, max_len = _FIELD_NAME_MIN_LENGTH, _FIELD_NAME_MAX_LENGTH
        else:
            min_len, max_len = _ENTITY_NAME_MIN_LENGTH, _ENTITY_NAME_MAX_LENGTH

        if not (min_len <= len(name) <= max_len) or not _NAME_RE.match(name):
            raise ValueError(
                f"Invalid {context} name {name!r}. Must start with a letter, "
                f"contain only letters and digits, and be {min_len}-{max_len} "
                "characters."
            )

    @staticmethod
    def _validate_field_constraints(
        ftype: EntityFieldDataType, field: EntityCreateFieldOptions
    ) -> None:
        """Validate caller-supplied per-field constraints.

        Rejects constraints that ``ftype`` does not accept (e.g.
        ``decimal_precision`` on ``STRING``), values outside the inclusive
        range declared in :data:`ENTITY_FIELD_CONSTRAINT_SPEC`, and
        ``min_value`` greater than or equal to ``max_value`` when both are
        supplied. Also enforces type-dependent required references:
        ``CHOICE_SET_SINGLE`` and ``CHOICE_SET_MULTIPLE`` need
        ``choice_set_id``; ``RELATIONSHIP`` needs ``reference_entity_name``.
        """
        if (
            ftype
            in (
                EntityFieldDataType.CHOICE_SET_SINGLE,
                EntityFieldDataType.CHOICE_SET_MULTIPLE,
            )
            and not field.choice_set_id
        ):
            raise ValueError(
                f"Field {field.field_name!r} of type {ftype.value} requires "
                "choice_set_id."
            )
        if (
            ftype is EntityFieldDataType.RELATIONSHIP
            and not field.reference_entity_name
        ):
            raise ValueError(
                f"Field {field.field_name!r} of type {ftype.value} requires "
                "reference_entity_name."
            )

        spec = ENTITY_FIELD_CONSTRAINT_SPEC.get(ftype, {})
        provided: Dict[str, Any] = {}
        for attr in ("length_limit", "max_value", "min_value", "decimal_precision"):
            value = getattr(field, attr)
            if value is not None:
                provided[attr] = value

        unsupported = [name for name in provided if name not in spec]
        if unsupported:
            allowed = ", ".join(sorted(spec.keys())) or "none"
            raise ValueError(
                f"Field {field.field_name!r} of type {ftype.value} does not accept "
                f"{', '.join(sorted(unsupported))}. Allowed constraints: {allowed}."
            )

        for name, value in provided.items():
            low, high = spec[name]
            if not (low <= value <= high):
                raise ValueError(
                    f"Field {field.field_name!r} of type {ftype.value}: "
                    f"{name}={value} is out of range [{low}, {high}]."
                )

        if (
            field.min_value is not None
            and field.max_value is not None
            and field.min_value >= field.max_value
        ):
            raise ValueError(
                f"Field {field.field_name!r}: min_value ({field.min_value}) must be "
                f"strictly less than max_value ({field.max_value})."
            )

    @staticmethod
    def _extract_entity_id(response: Response) -> str:
        """Return the new entity id from a create-entity response.

        Accepts both a bare JSON string id and a JSON object containing
        ``id`` or ``entityId``.
        """
        try:
            body = response.json()
        except Exception:
            return response.text.strip().strip('"')
        if isinstance(body, str):
            return body
        if isinstance(body, dict):
            for key in ("id", "Id", "entityId", "EntityId"):
                value = body.get(key)
                if isinstance(value, str):
                    return value
        return response.text.strip().strip('"')
