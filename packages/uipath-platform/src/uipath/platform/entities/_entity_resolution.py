from __future__ import annotations

import abc
import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, Optional

from ..common._bindings import (
    EntityResourceOverwrite,
    ResourceOverwrite,
    _resource_overwrites,
)
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..orchestrator._folder_service import FolderService
from .entities import (
    DataFabricEntityItem,
    Entity,
    EntityRouting,
    QueryRoutingOverrideContext,
)

FolderPathResolver = Callable[[str], Optional[str]]
AsyncFolderPathResolver = Callable[[str], Awaitable[Optional[str]]]
EntityByKeyFetcher = Callable[[str], Entity]
AsyncEntityByKeyFetcher = Callable[[str], Awaitable[Entity]]
EntityByNameFetcher = Callable[[str, Optional[str]], Entity]
AsyncEntityByNameFetcher = Callable[[str, Optional[str]], Awaitable[Entity]]


# ---------------------------------------------------------------------------
# Routing strategy
# ---------------------------------------------------------------------------


class RoutingStrategy(abc.ABC):
    """Strategy for resolving a ``QueryRoutingOverrideContext`` at query time."""

    @abc.abstractmethod
    def resolve(self) -> Optional[QueryRoutingOverrideContext]: ...

    @abc.abstractmethod
    async def resolve_async(self) -> Optional[QueryRoutingOverrideContext]: ...


class PreResolvedRoutingStrategy(RoutingStrategy):
    """Returns a routing context that was fully resolved at init time.

    Used after ``resolve_entity_set`` where all folder paths have already
    been converted to folder keys and the routing context is immutable.
    """

    def __init__(
        self,
        routing_context: QueryRoutingOverrideContext,
    ) -> None:
        self._routing_context = routing_context

    def resolve(self) -> Optional[QueryRoutingOverrideContext]:
        return self._routing_context

    async def resolve_async(self) -> Optional[QueryRoutingOverrideContext]:
        return self._routing_context

    @property
    def routing_context(self) -> QueryRoutingOverrideContext:
        return self._routing_context


class FoldersMapRoutingStrategy(RoutingStrategy):
    """Builds a routing context from a pre-populated folders map.

    Used when an ``EntitiesService`` is constructed with an explicit
    ``folders_map`` (and optional entity-name overrides) but *without* a
    pre-built routing context.  Folder paths in the map are resolved to
    folder keys lazily at query time via ``FolderService``.
    """

    def __init__(
        self,
        folders_map: Dict[str, str],
        effective_entity_names: Dict[str, str],
        folders_service: Optional[FolderService],
    ) -> None:
        self._folders_map = folders_map
        self._effective_entity_names = effective_entity_names
        self._folders_service = folders_service

    def resolve(self) -> Optional[QueryRoutingOverrideContext]:
        resolved = self._resolve_folder_paths()
        return build_resolution_routing_context(
            {
                name: (resolved or {}).get(path, path)
                for name, path in self._folders_map.items()
            },
            self._effective_entity_names,
        )

    async def resolve_async(self) -> Optional[QueryRoutingOverrideContext]:
        resolved = await self._resolve_folder_paths_async()
        return build_resolution_routing_context(
            {
                name: (resolved or {}).get(path, path)
                for name, path in self._folders_map.items()
            },
            self._effective_entity_names,
        )

    def _resolve_folder_paths(self) -> Optional[dict[str, str]]:
        folder_paths = set(self._folders_map.values())
        if not folder_paths:
            return None

        resolved: dict[str, str] = {}
        for folder_path in folder_paths:
            if self._folders_service is not None:
                folder_key = self._folders_service.retrieve_key(folder_path=folder_path)
                if folder_key is not None:
                    resolved[folder_path] = folder_key
                    continue
            resolved[folder_path] = folder_path
        return resolved

    async def _resolve_folder_paths_async(self) -> Optional[dict[str, str]]:
        folder_paths = set(self._folders_map.values())
        if not folder_paths:
            return None

        resolved: dict[str, str] = {}
        for folder_path in folder_paths:
            if self._folders_service is not None:
                folder_key = await self._folders_service.retrieve_key_async(
                    folder_path=folder_path
                )
                if folder_key is not None:
                    resolved[folder_path] = folder_key
                    continue
            resolved[folder_path] = folder_path
        return resolved


class ContextOverwriteRoutingStrategy(RoutingStrategy):
    """Builds a routing context lazily from ``_resource_overwrites``.

    This is the fallback for direct SDK usage where no ``folders_map`` or
    pre-resolved routing context exists.  Entity overwrites are read from
    the active ``ResourceOverwritesContext`` at query time.
    """

    def __init__(self, folders_service: Optional[FolderService]) -> None:
        self._folders_service = folders_service

    def resolve(self) -> Optional[QueryRoutingOverrideContext]:
        entity_overwrites = _get_entity_overwrites_from_context()
        if not entity_overwrites:
            return None

        folder_paths = {
            ow.folder_path for ow in entity_overwrites.values() if ow.folder_path
        }
        resolved = self._resolve_paths(folder_paths)
        return self._build(entity_overwrites, resolved)

    async def resolve_async(self) -> Optional[QueryRoutingOverrideContext]:
        entity_overwrites = _get_entity_overwrites_from_context()
        if not entity_overwrites:
            return None

        folder_paths = {
            ow.folder_path for ow in entity_overwrites.values() if ow.folder_path
        }
        resolved = await self._resolve_paths_async(folder_paths)
        return self._build(entity_overwrites, resolved)

    def _resolve_paths(self, folder_paths: set[str]) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for path in folder_paths:
            if self._folders_service is not None:
                key = self._folders_service.retrieve_key(folder_path=path)
                if key is not None:
                    resolved[path] = key
                    continue
            resolved[path] = path
        return resolved

    async def _resolve_paths_async(self, folder_paths: set[str]) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for path in folder_paths:
            if self._folders_service is not None:
                key = await self._folders_service.retrieve_key_async(folder_path=path)
                if key is not None:
                    resolved[path] = key
                    continue
            resolved[path] = path
        return resolved

    @staticmethod
    def _build(
        entity_overwrites: Dict[str, EntityResourceOverwrite],
        resolved: dict[str, str],
    ) -> Optional[QueryRoutingOverrideContext]:
        routings: list[EntityRouting] = []
        for original_name, overwrite in entity_overwrites.items():
            override_name = (
                overwrite.resource_identifier
                if overwrite.resource_identifier != original_name
                else None
            )
            folder_id = _resolve_overwrite_folder(overwrite, resolved)
            routings.append(
                EntityRouting(
                    entity_name=original_name,
                    folder_id=folder_id,
                    override_entity_name=override_name,
                )
            )

        if not routings:
            return None
        return QueryRoutingOverrideContext(entity_routings=routings)


def create_routing_strategy(
    *,
    folders_map: Optional[Dict[str, str]],
    effective_entity_names: Optional[Dict[str, str]],
    routing_context: Optional[QueryRoutingOverrideContext],
    folders_service: Optional[FolderService],
) -> RoutingStrategy:
    """Select the appropriate routing strategy based on init-time state."""
    if routing_context is not None:
        return PreResolvedRoutingStrategy(routing_context)
    if folders_map:
        return FoldersMapRoutingStrategy(
            folders_map,
            effective_entity_names or {},
            folders_service,
        )
    return ContextOverwriteRoutingStrategy(folders_service)


# ---------------------------------------------------------------------------
# Helpers shared across strategies
# ---------------------------------------------------------------------------


def _get_entity_overwrites_from_context() -> Dict[str, EntityResourceOverwrite]:
    """Extract entity overwrites from the active ResourceOverwritesContext."""
    context_overwrites = _resource_overwrites.get()
    if not context_overwrites:
        return {}

    result: Dict[str, EntityResourceOverwrite] = {}
    for key, overwrite in context_overwrites.items():
        if isinstance(overwrite, EntityResourceOverwrite):
            original_name = key.split(".", 1)[1] if "." in key else key
            result[original_name] = overwrite
    return result


def _resolve_overwrite_folder(
    overwrite: EntityResourceOverwrite,
    resolved: dict[str, str],
) -> str:
    """Return the folder key for an entity overwrite.

    Uses folder_id directly when present (already a key).
    Falls back to resolving folder_path through the resolved map.
    """
    if overwrite.folder_id:
        return overwrite.folder_id
    if overwrite.folder_path and resolved:
        return resolved.get(overwrite.folder_path, overwrite.folder_path)
    return overwrite.folder_identifier


# ---------------------------------------------------------------------------
# Resolution plan (used by resolve_entity_set)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EntityFetchByKey:
    entity_key: str


@dataclass(frozen=True)
class EntityFetchByName:
    entity_name: str
    folder_key: str


@dataclass(frozen=True)
class EntityResolutionDraft:
    fetch_by_key: list[EntityFetchByKey]
    fetch_by_name: list[EntityFetchByName]
    folders_map: dict[str, str]
    effective_entity_names: dict[str, str]
    folder_paths_to_resolve: set[str]


@dataclass(frozen=True)
class EntityResolutionPlan:
    fetch_by_key: list[EntityFetchByKey]
    fetch_by_name: list[EntityFetchByName]
    folders_map: dict[str, str]
    effective_entity_names: dict[str, str]
    routing_context: QueryRoutingOverrideContext | None


def create_resolution_draft(
    items: list[DataFabricEntityItem],
    context_overwrites: dict[str, ResourceOverwrite],
) -> EntityResolutionDraft:
    folders_map: dict[str, str] = {}
    effective_entity_names: dict[str, str] = {}
    folder_paths_to_resolve: set[str] = set()
    fetch_by_key: list[EntityFetchByKey] = []
    fetch_by_name: list[EntityFetchByName] = []

    for item in items:
        overwrite = context_overwrites.get(
            f"entity.{item.id}"
        ) or context_overwrites.get(f"entity.{item.name}")
        resolved_folder = item.folder_key

        if isinstance(overwrite, EntityResourceOverwrite):
            folder_changed = False
            if overwrite.folder_id:
                resolved_folder = overwrite.folder_id
                folder_changed = resolved_folder != item.folder_key
            elif overwrite.folder_path:
                resolved_folder = overwrite.folder_path
                folder_changed = True
                folder_paths_to_resolve.add(overwrite.folder_path)

            if overwrite.name != item.name or folder_changed:
                if overwrite.name != item.name:
                    effective_entity_names[item.name] = overwrite.name
                fetch_by_name.append(
                    EntityFetchByName(
                        entity_name=overwrite.name,
                        folder_key=resolved_folder,
                    )
                )
                folders_map[item.name] = resolved_folder
                continue

        fetch_by_key.append(EntityFetchByKey(entity_key=item.entity_key or item.id))
        folders_map[item.name] = resolved_folder

    return EntityResolutionDraft(
        fetch_by_key=fetch_by_key,
        fetch_by_name=fetch_by_name,
        folders_map=folders_map,
        effective_entity_names=effective_entity_names,
        folder_paths_to_resolve=folder_paths_to_resolve,
    )


def finalize_resolution_plan(
    draft: EntityResolutionDraft,
    resolve_folder_path: Callable[[str], Optional[str]],
) -> EntityResolutionPlan:
    resolved_paths: dict[str, str] = {}
    for folder_path in draft.folder_paths_to_resolve:
        resolved_paths[folder_path] = resolve_folder_path(folder_path) or folder_path

    resolved_folders_map = {
        entity_name: resolved_paths.get(folder_key, folder_key)
        for entity_name, folder_key in draft.folders_map.items()
    }
    resolved_fetch_by_name = [
        EntityFetchByName(
            entity_name=entry.entity_name,
            folder_key=resolved_paths.get(entry.folder_key, entry.folder_key),
        )
        for entry in draft.fetch_by_name
    ]

    return EntityResolutionPlan(
        fetch_by_key=draft.fetch_by_key,
        fetch_by_name=resolved_fetch_by_name,
        folders_map=resolved_folders_map,
        effective_entity_names=draft.effective_entity_names,
        routing_context=build_resolution_routing_context(
            resolved_folders_map,
            draft.effective_entity_names,
        ),
    )


def build_resolution_routing_context(
    folders_map: dict[str, str],
    effective_entity_names: dict[str, str],
) -> QueryRoutingOverrideContext | None:
    routings = [
        EntityRouting(
            entity_name=original_name,
            folder_id=folder_id,
            override_entity_name=effective_entity_names.get(original_name),
        )
        for original_name, folder_id in folders_map.items()
    ]
    if not routings:
        return None

    return QueryRoutingOverrideContext(entity_routings=routings)


def create_resolution_plan(
    items: list[DataFabricEntityItem],
    context_overwrites: dict[str, ResourceOverwrite],
    resolve_folder_path: FolderPathResolver,
) -> EntityResolutionPlan:
    draft = create_resolution_draft(items, context_overwrites)
    return finalize_resolution_plan(draft, resolve_folder_path)


async def create_resolution_plan_async(
    items: list[DataFabricEntityItem],
    context_overwrites: dict[str, ResourceOverwrite],
    resolve_folder_path: AsyncFolderPathResolver,
) -> EntityResolutionPlan:
    draft = create_resolution_draft(items, context_overwrites)
    folder_paths = list(draft.folder_paths_to_resolve)
    results = await asyncio.gather(*(resolve_folder_path(fp) for fp in folder_paths))
    resolved_paths = {
        fp: result or fp for fp, result in zip(folder_paths, results, strict=True)
    }

    return finalize_resolution_plan(
        draft,
        lambda folder_path: resolved_paths.get(folder_path, folder_path),
    )


def fetch_resolved_entities(
    plan: EntityResolutionPlan,
    retrieve_by_key: EntityByKeyFetcher,
    retrieve_by_name: EntityByNameFetcher,
    logger: logging.Logger,
) -> list[Entity]:
    entities: list[Entity] = []
    for key_entry in plan.fetch_by_key:
        try:
            entities.append(retrieve_by_key(key_entry.entity_key))
        except Exception:
            logger.warning(
                "Failed to fetch entity by key '%s', skipping.",
                key_entry.entity_key,
                exc_info=True,
            )

    for name_entry in plan.fetch_by_name:
        try:
            entities.append(
                retrieve_by_name(name_entry.entity_name, name_entry.folder_key)
            )
        except Exception:
            logger.warning(
                "Failed to fetch entity by name '%s' (folder_key=%s), skipping.",
                name_entry.entity_name,
                name_entry.folder_key,
                exc_info=True,
            )

    return entities


async def fetch_resolved_entities_async(
    plan: EntityResolutionPlan,
    retrieve_by_key: AsyncEntityByKeyFetcher,
    retrieve_by_name: AsyncEntityByNameFetcher,
    logger: logging.Logger,
) -> list[Entity]:
    async def _safe_fetch_by_key(entry: EntityFetchByKey) -> Optional[Entity]:
        try:
            return await retrieve_by_key(entry.entity_key)
        except Exception:
            logger.warning(
                "Failed to fetch entity by key '%s', skipping.",
                entry.entity_key,
                exc_info=True,
            )
            return None

    async def _safe_fetch_by_name(entry: EntityFetchByName) -> Optional[Entity]:
        try:
            return await retrieve_by_name(
                entry.entity_name,
                entry.folder_key,
            )
        except Exception:
            logger.warning(
                "Failed to fetch entity by name '%s' (folder_key=%s), skipping.",
                entry.entity_name,
                entry.folder_key,
                exc_info=True,
            )
            return None

    tasks = [_safe_fetch_by_key(entry) for entry in plan.fetch_by_key] + [
        _safe_fetch_by_name(entry) for entry in plan.fetch_by_name
    ]
    results = await asyncio.gather(*tasks)
    return [entity for entity in results if entity is not None]


def build_resolution_service(
    *,
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    folders_service: FolderService | None,
    plan: EntityResolutionPlan,
    service_factory: Callable[..., object],
) -> object:
    return service_factory(
        config=config,
        execution_context=execution_context,
        folders_service=folders_service,
        folders_map=plan.folders_map,
        entity_name_overrides=plan.effective_entity_names,
        routing_context=plan.routing_context,
    )
