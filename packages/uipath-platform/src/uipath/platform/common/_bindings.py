import functools
import inspect
import logging
from abc import ABC, abstractmethod
from contextvars import ContextVar, Token
from enum import StrEnum
from typing import (
    Annotated,
    Any,
    Callable,
    Coroutine,
    Literal,
    Optional,
    TypeVar,
    Union,
    get_args,
)

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    ValidationError,
    field_validator,
    model_validator,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ResourceOverwrite(BaseModel, ABC):
    """Abstract base class for resource overwrites.

    Subclasses must implement properties to provide resource and folder identifiers
    appropriate for their resource type.
    """

    model_config = ConfigDict(populate_by_name=True)

    @property
    @abstractmethod
    def resource_identifier(self) -> str:
        """The identifier used to reference this resource."""
        pass

    @property
    @abstractmethod
    def folder_identifier(self) -> str:
        """The folder location identifier for this resource."""
        pass


class GenericResourceOverwrite(ResourceOverwrite):
    resource_type: Literal[
        "process",
        "index",
        "app",
        "asset",
        "bucket",
        "mcpServer",
        "queue",
        "remoteA2aAgent",
        "memorySpace",
        "businessRule",
        # The Agents packager fills an ontology binding's folderPath with the folder
        # key (a GUID); OntologyService sends a GUID folder as the key, not a path.
        "ontology",
    ]
    name: str = Field(alias="name")
    folder_path: str = Field(alias="folderPath")

    @property
    def resource_identifier(self) -> str:
        return self.name

    @property
    def folder_identifier(self) -> str:
        return self.folder_path


class EntityResourceOverwrite(ResourceOverwrite):
    resource_type: Literal["entity"]
    name: str = Field(alias="name")
    folder_id: Optional[str] = Field(default=None, alias="folderId")
    folder_path: Optional[str] = Field(default=None, alias="folderPath")

    @model_validator(mode="after")
    def validate_folder_identifier(self) -> "EntityResourceOverwrite":
        if self.folder_id and self.folder_path:
            raise ValueError("Only one of folderId or folderPath may be provided.")
        if not self.folder_id and not self.folder_path:
            raise ValueError("Either folderId or folderPath must be provided.")
        return self

    @property
    def resource_identifier(self) -> str:
        return self.name

    @property
    def folder_identifier(self) -> str:
        return self.folder_id or self.folder_path or ""


class ConnectionResourceOverwrite(ResourceOverwrite):
    resource_type: Literal["connection"]
    # In eval context, studio web provides "ConnectionId".
    connection_id: str = Field(
        alias="connectionId",
        validation_alias=AliasChoices("connectionId", "ConnectionId"),
    )
    folder_key: str = Field(alias="folderKey")

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
    )

    @property
    def resource_identifier(self) -> str:
        return self.connection_id

    @property
    def folder_identifier(self) -> str:
        return self.folder_key


class VersionMode(StrEnum):
    """How a skill bundle version is chosen.

    ``pinned`` uses a fixed version; ``latest`` takes the newest one at run start.
    """

    PINNED = "pinned"
    LATEST = "latest"


def version_for_mode(mode: VersionMode, version: Optional[str]) -> Optional[str]:
    """The version a skill bundle reference keeps under ``mode``.

    Args:
        mode: The reference's version mode.
        version: The version it declares, if any.

    Returns:
        ``version`` when pinned, ``None`` for ``latest``.

    Raises:
        ValueError: Pinned without a version.
    """
    if mode is VersionMode.LATEST:
        return None
    if not version:
        raise ValueError("a pinned skill bundle needs a version")
    return version


class SkillBundleResourceOverwrite(ResourceOverwrite):
    """A deploy-time override of an agent's skill bundle binding.

    Like the other bindings, an entry replaces the whole binding: it carries
    ``name``, ``folderPath`` and ``versionMode``, plus ``version`` when pinned.
    Its ``name`` retargets the bundle that is looked up; the agent-side name of
    the binding stays what the agent declared. Apply it with
    ``uipath.platform.skills._overwrites.apply_skill_bundle_overwrite``.

    ``ResourceOverwriteParser.parse`` keeps an entry that is not a valid
    binding as ``invalid(problem)``, so the skills loader fails that bundle
    instead of falling back to the declared binding. Constructing the class
    directly validates like any other model.
    """

    resource_type: Literal["skillBundle"]
    name: str = Field(alias="name")
    folder_path: str = Field(alias="folderPath")
    version_mode: VersionMode = Field(alias="versionMode")
    version: Optional[str] = Field(default=None, alias="version")
    problem: Optional[str] = Field(default=None, exclude=True)
    """Why the entry is not a valid binding; ``None`` when it is."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    @field_validator("name", "folder_path")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError(
                "a skillBundle overwrite needs a non-blank name and folderPath"
            )
        return value

    @field_validator("version", mode="before")
    @classmethod
    def _blank_is_unset(cls, value: Any) -> Any:
        # A cleared form field arrives as "", which is no version.
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _version_matches_mode(self) -> "SkillBundleResourceOverwrite":
        self.version = version_for_mode(self.version_mode, self.version)
        return self

    @classmethod
    def invalid(cls, problem: str) -> "SkillBundleResourceOverwrite":
        """An entry that is not a valid binding, kept so its bundle can fail.

        Args:
            problem: Why the entry is invalid.

        Returns:
            An entry with ``problem`` set and every other field empty.
        """
        return cls.model_construct(
            resource_type="skillBundle",
            name="",
            folder_path="",
            version_mode=VersionMode.LATEST,
            version=None,
            problem=problem,
        )

    @property
    def resource_identifier(self) -> str:
        return self.name

    @property
    def folder_identifier(self) -> str:
        return self.folder_path


ResourceOverwriteUnion = Annotated[
    Union[
        GenericResourceOverwrite,
        EntityResourceOverwrite,
        ConnectionResourceOverwrite,
        SkillBundleResourceOverwrite,
    ],
    Field(discriminator="resource_type"),
]

_KNOWN_RESOURCE_TYPES: frozenset[str] = frozenset(
    resource_type
    for model in get_args(get_args(ResourceOverwriteUnion)[0])
    for resource_type in get_args(model.model_fields["resource_type"].annotation)
)


class ResourceOverwriteParser:
    """Parser for resource overwrite configurations.

    Handles parsing of resource overwrites from key-value pairs where the key
    contains the resource type prefix (e.g., "process.name", "connection.key").
    """

    _adapter: TypeAdapter[ResourceOverwriteUnion] = TypeAdapter(ResourceOverwriteUnion)

    @classmethod
    def knows(cls, key: str) -> bool:
        """Whether this SDK has a model for the resource type ``key`` starts with.

        Args:
            key: The resource key (e.g., "process.MyProcess").

        Returns:
            ``False`` for a kind added after this SDK version, which ``parse``
            would reject.
        """
        return key.split(".")[0] in _KNOWN_RESOURCE_TYPES

    @classmethod
    def parse(cls, key: str, value: dict[str, Any]) -> ResourceOverwrite:
        """Parse a resource overwrite from a key-value pair.

        Extracts the resource type from the key prefix and injects it into the value
        for discriminated union validation.

        Args:
            key: The resource key (e.g., "process.MyProcess", "connection.abc-123")
            value: The resource data dictionary

        Returns:
            The appropriate ResourceOverwrite subclass instance. An invalid
            ``skillBundle`` entry comes back as
            ``SkillBundleResourceOverwrite.invalid(problem)`` instead of raising.
        """
        resource_type = key.split(".")[0]
        normalized_value = cls._normalize_value(resource_type, value)
        value_with_type = {"resource_type": resource_type, **normalized_value}
        try:
            return cls._adapter.validate_python(value_with_type)
        except ValidationError as e:
            if resource_type != "skillBundle":
                raise
            return SkillBundleResourceOverwrite.invalid(
                _first_problem(e, resource_type)
            )

    @staticmethod
    def _normalize_value(resource_type: str, value: dict[str, Any]) -> dict[str, Any]:
        if resource_type != "entity":
            return value

        normalized = dict(value)
        if "folderId" in normalized:
            normalized["folder_id"] = normalized.pop("folderId")
        if "folderPath" in normalized:
            normalized["folder_path"] = normalized.pop("folderPath")

        return normalized


def _first_problem(error: ValidationError, resource_type: str) -> str:
    """The first validation error on one line, ``<field>: <message>``."""
    first = error.errors()[0]
    # The union adds the discriminator value in front of the field.
    loc = [str(part) for part in first["loc"]]
    if loc and loc[0] == resource_type:
        loc = loc[1:]
    field = ".".join(loc)
    return f"{field}: {first['msg']}" if field else str(first["msg"])


_resource_overwrites: ContextVar[Optional[dict[str, ResourceOverwrite]]] = ContextVar(
    "resource_overwrites", default=None
)


class ResourceOverwritesContext:
    def __init__(
        self,
        get_overwrites_callable: Callable[
            [], Coroutine[Any, Any, dict[str, ResourceOverwrite]]
        ],
    ):
        self.get_overwrites_callable = get_overwrites_callable
        self._token: Optional[Token[Optional[dict[str, ResourceOverwrite]]]] = None
        self.overwrites_count = 0

    async def __aenter__(self) -> "ResourceOverwritesContext":
        existing = _resource_overwrites.get()
        if existing is not None:
            logger.warning(
                "Entering ResourceOverwritesContext while another context is already active (%d existing overwrite(s))",
                len(existing),
            )
        overwrites = await self.get_overwrites_callable()
        self._token = _resource_overwrites.set(overwrites)
        self.overwrites_count = len(overwrites)
        if overwrites:
            logger.info(
                "Resource overwrites context entered: %d overwrite(s) loaded, keys=%s",
                len(overwrites),
                list(overwrites.keys()),
            )
        else:
            logger.debug("Resource overwrites context entered: no overwrites loaded")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._token:
            logger.debug(
                "Resource overwrites context exited: %d overwrite(s) cleared",
                self.overwrites_count,
            )
            _resource_overwrites.reset(self._token)


_OTHER_FOLDER_IDENTIFIER = {"folder_path": "folder_key", "folder_key": "folder_path"}


def _clear_folder_identifier_replaced_by_binding(
    all_args: dict[str, Any],
    sig: inspect.Signature,
    folder_identifier: str,
    bound_folder: Optional[str],
) -> None:
    """Clear the caller's other folder identifier when a binding names a folder.

    header_folder() rejects a folder_key and a folder_path together.
    """
    other_folder_identifier = _OTHER_FOLDER_IDENTIFIER.get(folder_identifier)
    if (
        not bound_folder
        or other_folder_identifier is None
        or other_folder_identifier not in sig.parameters
    ):
        return
    cleared = all_args.get(other_folder_identifier)
    all_args[other_folder_identifier] = None
    if cleared is not None:
        logger.debug(
            "Resource overwrite cleared %s='%s' in favour of bound %s='%s'",
            other_folder_identifier,
            cleared,
            folder_identifier,
            bound_folder,
        )


def resource_override(
    resource_type: str,
    resource_identifier: str = "name",
    folder_identifier: str = "folder_path",
) -> Callable[..., Any]:
    """Decorator for applying resource overrides for an overridable resource.

    It checks the current ContextVar to identify the requested overrides and, if any key matches, it invokes the decorated function
    with the extracted resource and folder identifiers.

    Args:
        resource_type: Type of resource to check for overrides (e.g., "asset", "bucket")
        resource_identifier: Key name for the resource ID in override data (default: "name")
        folder_identifier: Key name for the folder path in override data (default: "folder_path")

    Returns:
        Decorated function that receives overridden resource identifiers when applicable

    Note:
        Must be applied BEFORE the @traced decorator to ensure proper execution order.
    """

    def decorator(func: Callable[..., Any]):
        sig = inspect.signature(func)

        def process_args(args, kwargs) -> dict[str, Any]:
            """Process arguments and apply resource overrides if applicable."""
            # convert both args and kwargs to single dict
            bound = sig.bind_partial(*args, **kwargs)
            bound.apply_defaults()
            all_args = dict(bound.arguments)
            if (
                "kwargs" in sig.parameters
                and sig.parameters["kwargs"].kind == inspect.Parameter.VAR_KEYWORD
            ):
                extra_kwargs = all_args.pop("kwargs", {})
                all_args.update(extra_kwargs)

            # Get overwrites from context variable
            context_overwrites = _resource_overwrites.get()

            if context_overwrites is not None:
                resource_identifier_value = all_args.get(resource_identifier)
                folder_identifier_value = all_args.get(folder_identifier)

                key = f"{resource_type}.{resource_identifier_value}"
                # try to apply folder path, fallback to resource_type.resource_name
                if folder_identifier_value:
                    key = (
                        f"{key}.{folder_identifier_value}"
                        if f"{key}.{folder_identifier_value}" in context_overwrites
                        else key
                    )

                matched_overwrite = context_overwrites.get(key)

                # Apply the matched overwrite
                if matched_overwrite is not None:
                    old_resource = all_args.get(resource_identifier)
                    old_folder = all_args.get(folder_identifier)
                    if resource_identifier in sig.parameters:
                        all_args[resource_identifier] = (
                            matched_overwrite.resource_identifier
                        )
                    if folder_identifier in sig.parameters:
                        all_args[folder_identifier] = (
                            matched_overwrite.folder_identifier
                        )
                        _clear_folder_identifier_replaced_by_binding(
                            all_args,
                            sig,
                            folder_identifier,
                            matched_overwrite.folder_identifier,
                        )
                    logger.debug(
                        "Resource overwrite applied for %s on %s: %s='%s' -> '%s', %s='%s' -> '%s'",
                        resource_type,
                        func.__name__,
                        resource_identifier,
                        old_resource,
                        matched_overwrite.resource_identifier,
                        folder_identifier,
                        old_folder,
                        matched_overwrite.folder_identifier,
                    )
                else:
                    logger.info(
                        "No resource overwrite matched for %s key='%s' on %s",
                        resource_type,
                        key,
                        func.__name__,
                    )

            return all_args

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                all_args = process_args(args, kwargs)
                return await func(**all_args)

            return async_wrapper
        else:

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                all_args = process_args(args, kwargs)
                return func(**all_args)

            return wrapper

    return decorator
