from typing import Any, Dict, List, Optional

from uipath.core.tracing import traced

from ..common._base_service import BaseService
from ..common._config import UiPathApiConfig
from ..common._execution_context import UiPathExecutionContext
from ..common._folder_context import FolderContext, header_folder
from ..common._models import Endpoint, RequestSpec
from ..common.paging import PagedResult
from ..common.validation import validate_pagination_params
from .skills import Skill, SkillVersion, SkillVersionStatus, VersionBumpLevel

MAX_PAGE_SIZE = 1000
MAX_SKIP_OFFSET = 10000


class SkillsService(FolderContext, BaseService):
    """Service for managing UiPath Skills (vdbs).

    Skills are named, versioned, folder-scoped resources whose content is the
    prompt an agent uses when invoking the skill as a tool. Each skill has a
    lifecycle of Draft -> Published -> Deprecated -> Retired and tracks an
    optional current draft alongside the published version.
    """

    def __init__(
        self, config: UiPathApiConfig, execution_context: UiPathExecutionContext
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    # --- Skills ---

    @traced(name="skills_list", run_type="uipath")
    def list(
        self,
        *,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        name: Optional[str] = None,
        include_content: bool = False,
        skip: int = 0,
        top: int = 100,
    ) -> PagedResult[Skill]:
        """List skills in the current folder.

        Args:
            folder_path: Folder path scope (mutually exclusive with folder_key).
            folder_key: Folder key scope.
            name: Optional contains-match on skill name.
            include_content: When true, every version on every skill is returned
                with its `content` populated (a heavier read).
            skip: OData $skip (default 0, max 10000).
            top: OData $top (default 100, max 1000).

        Returns:
            PagedResult[Skill]: A page of skills with offset pagination metadata.
        """
        validate_pagination_params(
            skip=skip, top=top, max_skip=MAX_SKIP_OFFSET, max_top=MAX_PAGE_SIZE
        )
        spec = self._list_spec(
            folder_path=folder_path,
            folder_key=folder_key,
            name=name,
            include_content=include_content,
            skip=skip,
            top=top,
        )
        response = self.request(
            spec.method, url=spec.endpoint, params=spec.params, headers=spec.headers
        ).json()
        items = response.get("value", [])
        skills = [Skill.model_validate(item) for item in items]
        return PagedResult(items=skills, has_more=len(items) == top, skip=skip, top=top)

    @traced(name="skills_list", run_type="uipath")
    async def list_async(
        self,
        *,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
        name: Optional[str] = None,
        include_content: bool = False,
        skip: int = 0,
        top: int = 100,
    ) -> PagedResult[Skill]:
        """Async version of list()."""
        validate_pagination_params(
            skip=skip, top=top, max_skip=MAX_SKIP_OFFSET, max_top=MAX_PAGE_SIZE
        )
        spec = self._list_spec(
            folder_path=folder_path,
            folder_key=folder_key,
            name=name,
            include_content=include_content,
            skip=skip,
            top=top,
        )
        response = (
            await self.request_async(
                spec.method, url=spec.endpoint, params=spec.params, headers=spec.headers
            )
        ).json()
        items = response.get("value", [])
        skills = [Skill.model_validate(item) for item in items]
        return PagedResult(items=skills, has_more=len(items) == top, skip=skip, top=top)

    @traced(name="skills_list_across_folders", run_type="uipath")
    def list_across_folders(
        self,
        *,
        include_content: bool = False,
    ) -> List[Skill]:
        """List skills the caller has access to across every folder."""
        spec = self._list_across_folders_spec(include_content=include_content)
        response = self.request(
            spec.method, url=spec.endpoint, params=spec.params, headers=spec.headers
        ).json()
        items = response.get("value", [])
        return [Skill.model_validate(item) for item in items]

    @traced(name="skills_list_across_folders", run_type="uipath")
    async def list_across_folders_async(
        self,
        *,
        include_content: bool = False,
    ) -> List[Skill]:
        """Async version of list_across_folders()."""
        spec = self._list_across_folders_spec(include_content=include_content)
        response = (
            await self.request_async(
                spec.method, url=spec.endpoint, params=spec.params, headers=spec.headers
            )
        ).json()
        items = response.get("value", [])
        return [Skill.model_validate(item) for item in items]

    @traced(name="skills_retrieve", run_type="uipath")
    def retrieve(
        self,
        *,
        key: Optional[str] = None,
        name: Optional[str] = None,
        include_content: bool = True,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> Skill:
        """Retrieve a single skill by key or by name.

        Both lookups go through the OData ``$filter`` form — the single-entity
        URL ``/Skills({key})`` is not currently routed on the BE (returns 405).
        With ``include_content=True`` (the default), the skill's ``versions``
        array includes the prompt body; callers that need a specific version's
        content should look it up there rather than calling ``get_version``,
        whose bound-function URL is also unroutable on the current BE.

        Args:
            key: Skill identifier (Guid). When set, takes precedence over name.
            name: Skill name.
            include_content: When true (default), populate ``versions[].content``.
            folder_path: Folder path scope.
            folder_key: Folder key scope.

        Returns:
            Skill: The matching skill.

        Raises:
            ValueError: If neither key nor name is provided.
            LookupError: If no skill matches the criteria.
        """
        spec = self._retrieve_by_filter_spec(
            key=key,
            name=name,
            include_content=include_content,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        response = self.request(
            spec.method,
            url=spec.endpoint,
            params=spec.params,
            headers=spec.headers,
        ).json()
        items = response.get("value", [])
        if not items:
            criterion = f"key '{key}'" if key else f"name '{name}'"
            raise LookupError(f"Skill with {criterion} not found")
        return Skill.model_validate(items[0])

    @traced(name="skills_retrieve", run_type="uipath")
    async def retrieve_async(
        self,
        *,
        key: Optional[str] = None,
        name: Optional[str] = None,
        include_content: bool = True,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> Skill:
        """Async version of retrieve()."""
        spec = self._retrieve_by_filter_spec(
            key=key,
            name=name,
            include_content=include_content,
            folder_key=folder_key,
            folder_path=folder_path,
        )
        response = (
            await self.request_async(
                spec.method,
                url=spec.endpoint,
                params=spec.params,
                headers=spec.headers,
            )
        ).json()
        items = response.get("value", [])
        if not items:
            criterion = f"key '{key}'" if key else f"name '{name}'"
            raise LookupError(f"Skill with {criterion} not found")
        return Skill.model_validate(items[0])

    @traced(name="skills_create", run_type="uipath")
    def create(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        grace_period_days: Optional[int] = None,
        content: Optional[str] = None,
        version: Optional[str] = None,
        tags: Optional[List[str]] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> Skill:
        """Create a new skill (and optionally seed an initial draft version).

        Args:
            name: Kebab-case skill name (matches `^[a-z0-9]+(-[a-z0-9]+)*$`).
            description: Optional description (<=1024 chars).
            grace_period_days: Deprecation grace period. Defaults to 30 server-side.
            content: Optional initial draft content (prompt text).
            version: Optional initial semver (e.g. "0.0.1").
            tags: Optional tag list.
            folder_path: Folder path scope.
            folder_key: Folder key scope.
        """
        spec = self._create_spec(
            name=name,
            description=description,
            grace_period_days=grace_period_days,
            content=content,
            version=version,
            tags=tags,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = self.request(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        ).json()
        return Skill.model_validate(response)

    @traced(name="skills_create", run_type="uipath")
    async def create_async(
        self,
        *,
        name: str,
        description: Optional[str] = None,
        grace_period_days: Optional[int] = None,
        content: Optional[str] = None,
        version: Optional[str] = None,
        tags: Optional[List[str]] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> Skill:
        """Async version of create()."""
        spec = self._create_spec(
            name=name,
            description=description,
            grace_period_days=grace_period_days,
            content=content,
            version=version,
            tags=tags,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = (
            await self.request_async(
                spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
            )
        ).json()
        return Skill.model_validate(response)

    @traced(name="skills_update", run_type="uipath")
    def update(
        self,
        *,
        key: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        grace_period_days: Optional[int] = None,
        tags: Optional[List[str]] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> Skill:
        """Update skill metadata (does not touch versions or content)."""
        spec = self._update_spec(
            key=key,
            name=name,
            description=description,
            grace_period_days=grace_period_days,
            tags=tags,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = self.request(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        ).json()
        return Skill.model_validate(response)

    @traced(name="skills_update", run_type="uipath")
    async def update_async(
        self,
        *,
        key: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        grace_period_days: Optional[int] = None,
        tags: Optional[List[str]] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> Skill:
        """Async version of update()."""
        spec = self._update_spec(
            key=key,
            name=name,
            description=description,
            grace_period_days=grace_period_days,
            tags=tags,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = (
            await self.request_async(
                spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
            )
        ).json()
        return Skill.model_validate(response)

    @traced(name="skills_delete", run_type="uipath")
    def delete(
        self,
        *,
        key: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> None:
        """Delete a skill and all its versions."""
        spec = self._delete_spec(
            key=key, folder_path=folder_path, folder_key=folder_key
        )
        self.request(spec.method, url=spec.endpoint, headers=spec.headers)

    @traced(name="skills_delete", run_type="uipath")
    async def delete_async(
        self,
        *,
        key: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> None:
        """Async version of delete()."""
        spec = self._delete_spec(
            key=key, folder_path=folder_path, folder_key=folder_key
        )
        await self.request_async(spec.method, url=spec.endpoint, headers=spec.headers)

    # --- Versions ---

    @traced(name="skills_get_draft", run_type="uipath")
    def get_draft(
        self,
        *,
        key: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> SkillVersion:
        """Get the current draft version, if any.

        Raises:
            LookupError: If there is no current draft.
        """
        spec = self._draft_spec(key=key, folder_path=folder_path, folder_key=folder_key)
        try:
            response = self.request(
                spec.method, url=spec.endpoint, headers=spec.headers
            ).json()
        except Exception as e:
            raise LookupError(f"Skill '{key}' has no draft version") from e
        return SkillVersion.model_validate(response)

    @traced(name="skills_get_draft", run_type="uipath")
    async def get_draft_async(
        self,
        *,
        key: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> SkillVersion:
        """Async version of get_draft()."""
        spec = self._draft_spec(key=key, folder_path=folder_path, folder_key=folder_key)
        try:
            response = (
                await self.request_async(
                    spec.method, url=spec.endpoint, headers=spec.headers
                )
            ).json()
        except Exception as e:
            raise LookupError(f"Skill '{key}' has no draft version") from e
        return SkillVersion.model_validate(response)

    @traced(name="skills_list_versions", run_type="uipath")
    def list_versions(
        self,
        *,
        key: str,
        status: Optional[SkillVersionStatus] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> List[SkillVersion]:
        """List all versions of a skill, optionally filtered by status."""
        spec = self._list_versions_spec(
            key=key, status=status, folder_path=folder_path, folder_key=folder_key
        )
        response = self.request(
            spec.method, url=spec.endpoint, params=spec.params, headers=spec.headers
        ).json()
        items = response.get("value", [])
        return [SkillVersion.model_validate(item) for item in items]

    @traced(name="skills_list_versions", run_type="uipath")
    async def list_versions_async(
        self,
        *,
        key: str,
        status: Optional[SkillVersionStatus] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> List[SkillVersion]:
        """Async version of list_versions()."""
        spec = self._list_versions_spec(
            key=key, status=status, folder_path=folder_path, folder_key=folder_key
        )
        response = (
            await self.request_async(
                spec.method, url=spec.endpoint, params=spec.params, headers=spec.headers
            )
        ).json()
        items = response.get("value", [])
        return [SkillVersion.model_validate(item) for item in items]

    @traced(name="skills_get_version", run_type="uipath")
    def get_version(
        self,
        *,
        key: str,
        version_id: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> SkillVersion:
        """Get a specific version by id (always includes content)."""
        spec = self._get_version_spec(
            key=key,
            version_id=version_id,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        try:
            response = self.request(
                spec.method, url=spec.endpoint, params=spec.params, headers=spec.headers
            ).json()
        except Exception as e:
            raise LookupError(
                f"Skill '{key}' has no version with id '{version_id}'"
            ) from e
        return SkillVersion.model_validate(response)

    @traced(name="skills_get_version", run_type="uipath")
    async def get_version_async(
        self,
        *,
        key: str,
        version_id: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> SkillVersion:
        """Async version of get_version()."""
        spec = self._get_version_spec(
            key=key,
            version_id=version_id,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        try:
            response = (
                await self.request_async(
                    spec.method,
                    url=spec.endpoint,
                    params=spec.params,
                    headers=spec.headers,
                )
            ).json()
        except Exception as e:
            raise LookupError(
                f"Skill '{key}' has no version with id '{version_id}'"
            ) from e
        return SkillVersion.model_validate(response)

    @traced(name="skills_create_version", run_type="uipath")
    def create_version(
        self,
        *,
        key: str,
        bump_level: VersionBumpLevel = VersionBumpLevel.PATCH,
        content: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> SkillVersion:
        """Create a new draft version off the most recent published version."""
        spec = self._create_version_spec(
            key=key,
            bump_level=bump_level,
            content=content,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = self.request(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        ).json()
        return SkillVersion.model_validate(response)

    @traced(name="skills_create_version", run_type="uipath")
    async def create_version_async(
        self,
        *,
        key: str,
        bump_level: VersionBumpLevel = VersionBumpLevel.PATCH,
        content: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> SkillVersion:
        """Async version of create_version()."""
        spec = self._create_version_spec(
            key=key,
            bump_level=bump_level,
            content=content,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = (
            await self.request_async(
                spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
            )
        ).json()
        return SkillVersion.model_validate(response)

    @traced(name="skills_update_version", run_type="uipath")
    def update_version(
        self,
        *,
        key: str,
        version_id: str,
        content: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> SkillVersion:
        """Update the content of a draft version."""
        spec = self._update_version_spec(
            key=key,
            version_id=version_id,
            content=content,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = self.request(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        ).json()
        return SkillVersion.model_validate(response)

    @traced(name="skills_update_version", run_type="uipath")
    async def update_version_async(
        self,
        *,
        key: str,
        version_id: str,
        content: Optional[str] = None,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> SkillVersion:
        """Async version of update_version()."""
        spec = self._update_version_spec(
            key=key,
            version_id=version_id,
            content=content,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = (
            await self.request_async(
                spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
            )
        ).json()
        return SkillVersion.model_validate(response)

    @traced(name="skills_discard_version", run_type="uipath")
    def discard_version(
        self,
        *,
        key: str,
        version_id: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> None:
        """Discard a draft version (irreversible)."""
        spec = self._version_action_spec(
            key=key,
            action="DiscardVersion",
            version_id=version_id,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        self.request(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )

    @traced(name="skills_discard_version", run_type="uipath")
    async def discard_version_async(
        self,
        *,
        key: str,
        version_id: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> None:
        """Async version of discard_version()."""
        spec = self._version_action_spec(
            key=key,
            action="DiscardVersion",
            version_id=version_id,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        await self.request_async(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        )

    @traced(name="skills_publish_version", run_type="uipath")
    def publish_version(
        self,
        *,
        key: str,
        version_id: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> SkillVersion:
        """Publish a draft version, making it the new published version."""
        return self._invoke_version_state_transition(
            key=key,
            action="PublishVersion",
            version_id=version_id,
            folder_path=folder_path,
            folder_key=folder_key,
        )

    @traced(name="skills_publish_version", run_type="uipath")
    async def publish_version_async(
        self,
        *,
        key: str,
        version_id: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> SkillVersion:
        """Async version of publish_version()."""
        return await self._invoke_version_state_transition_async(
            key=key,
            action="PublishVersion",
            version_id=version_id,
            folder_path=folder_path,
            folder_key=folder_key,
        )

    @traced(name="skills_deprecate_version", run_type="uipath")
    def deprecate_version(
        self,
        *,
        key: str,
        version_id: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> SkillVersion:
        """Mark a published version as deprecated."""
        return self._invoke_version_state_transition(
            key=key,
            action="DeprecateVersion",
            version_id=version_id,
            folder_path=folder_path,
            folder_key=folder_key,
        )

    @traced(name="skills_deprecate_version", run_type="uipath")
    async def deprecate_version_async(
        self,
        *,
        key: str,
        version_id: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> SkillVersion:
        """Async version of deprecate_version()."""
        return await self._invoke_version_state_transition_async(
            key=key,
            action="DeprecateVersion",
            version_id=version_id,
            folder_path=folder_path,
            folder_key=folder_key,
        )

    @traced(name="skills_retire_version", run_type="uipath")
    def retire_version(
        self,
        *,
        key: str,
        version_id: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> SkillVersion:
        """Retire a deprecated version (terminal state)."""
        return self._invoke_version_state_transition(
            key=key,
            action="RetireVersion",
            version_id=version_id,
            folder_path=folder_path,
            folder_key=folder_key,
        )

    @traced(name="skills_retire_version", run_type="uipath")
    async def retire_version_async(
        self,
        *,
        key: str,
        version_id: str,
        folder_path: Optional[str] = None,
        folder_key: Optional[str] = None,
    ) -> SkillVersion:
        """Async version of retire_version()."""
        return await self._invoke_version_state_transition_async(
            key=key,
            action="RetireVersion",
            version_id=version_id,
            folder_path=folder_path,
            folder_key=folder_key,
        )

    # --- helpers ---

    def _invoke_version_state_transition(
        self,
        *,
        key: str,
        action: str,
        version_id: str,
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> SkillVersion:
        spec = self._version_action_spec(
            key=key,
            action=action,
            version_id=version_id,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = self.request(
            spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
        ).json()
        return SkillVersion.model_validate(response)

    async def _invoke_version_state_transition_async(
        self,
        *,
        key: str,
        action: str,
        version_id: str,
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> SkillVersion:
        spec = self._version_action_spec(
            key=key,
            action=action,
            version_id=version_id,
            folder_path=folder_path,
            folder_key=folder_key,
        )
        response = (
            await self.request_async(
                spec.method, url=spec.endpoint, json=spec.json, headers=spec.headers
            )
        ).json()
        return SkillVersion.model_validate(response)

    # --- spec builders ---

    def _list_spec(
        self,
        *,
        folder_path: Optional[str],
        folder_key: Optional[str],
        name: Optional[str],
        include_content: bool,
        skip: int,
        top: int,
    ) -> RequestSpec:
        params: Dict[str, Any] = {"$skip": skip, "$top": top}
        if include_content:
            params["includeContent"] = "true"
        if name:
            escaped = name.replace("'", "''")
            params["$filter"] = f"contains(tolower(Name), tolower('{escaped}'))"
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/ecs_/v2/Skills"),
            params=params,
            headers={**header_folder(folder_key, folder_path)},
        )

    def _list_across_folders_spec(self, *, include_content: bool) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"/ecs_/v2/Skills/AllAcrossFolders(includeContent={'true' if include_content else 'false'})"
            ),
        )

    def _retrieve_by_filter_spec(
        self,
        *,
        key: Optional[str],
        name: Optional[str],
        include_content: bool,
        folder_key: Optional[str],
        folder_path: Optional[str],
    ) -> RequestSpec:
        """Build an OData filter request that retrieves at most one skill.

        The BE does not currently route the single-entity URL
        ``/Skills({key})`` (returns 405), so both key and name lookups share
        the same filter-based shape. Caller chooses which to send.
        """
        if key:
            filter_expr = f"id eq {key}"
        elif name:
            escaped = name.replace("'", "''")
            filter_expr = f"name eq '{escaped}'"
        else:
            raise ValueError("Must specify a skill key or skill name")

        params: Dict[str, Any] = {"$filter": filter_expr, "$top": 1}
        if include_content:
            params["includeContent"] = "true"
        return RequestSpec(
            method="GET",
            endpoint=Endpoint("/ecs_/v2/Skills"),
            params=params,
            headers={**header_folder(folder_key, folder_path)},
        )

    def _create_spec(
        self,
        *,
        name: str,
        description: Optional[str],
        grace_period_days: Optional[int],
        content: Optional[str],
        version: Optional[str],
        tags: Optional[List[str]],
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> RequestSpec:
        body: Dict[str, Any] = {"Name": name}
        if description is not None:
            body["Description"] = description
        if grace_period_days is not None:
            body["GracePeriodDays"] = grace_period_days
        if content is not None:
            body["Content"] = content
        if version is not None:
            body["Version"] = version
        if tags is not None:
            body["Tags"] = tags
        return RequestSpec(
            method="POST",
            endpoint=Endpoint("/ecs_/v2/Skills/Create"),
            json=body,
            headers={**header_folder(folder_key, folder_path)},
        )

    def _update_spec(
        self,
        *,
        key: str,
        name: Optional[str],
        description: Optional[str],
        grace_period_days: Optional[int],
        tags: Optional[List[str]],
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> RequestSpec:
        body: Dict[str, Any] = {}
        if name is not None:
            body["Name"] = name
        if description is not None:
            body["Description"] = description
        if grace_period_days is not None:
            body["GracePeriodDays"] = grace_period_days
        if tags is not None:
            body["Tags"] = tags
        return RequestSpec(
            method="PATCH",
            endpoint=Endpoint(f"/ecs_/v2/Skills({key})"),
            json=body,
            headers={**header_folder(folder_key, folder_path)},
        )

    def _delete_spec(
        self,
        *,
        key: str,
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> RequestSpec:
        return RequestSpec(
            method="DELETE",
            endpoint=Endpoint(f"/ecs_/v2/Skills({key})"),
            headers={**header_folder(folder_key, folder_path)},
        )

    def _draft_spec(
        self,
        *,
        key: str,
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(f"/ecs_/v2/Skills({key})/Draft"),
            headers={**header_folder(folder_key, folder_path)},
        )

    def _list_versions_spec(
        self,
        *,
        key: str,
        status: Optional[SkillVersionStatus],
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> RequestSpec:
        if status is not None:
            endpoint = Endpoint(
                f"/ecs_/v2/Skills({key})/ListVersions(status='{status.name.capitalize()}')"
            )
        else:
            endpoint = Endpoint(f"/ecs_/v2/Skills({key})/ListVersions()")
        return RequestSpec(
            method="GET",
            endpoint=endpoint,
            headers={**header_folder(folder_key, folder_path)},
        )

    def _get_version_spec(
        self,
        *,
        key: str,
        version_id: str,
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"/ecs_/v2/Skills({key})/GetVersion(versionId={version_id})"
            ),
            headers={**header_folder(folder_key, folder_path)},
        )

    def _create_version_spec(
        self,
        *,
        key: str,
        bump_level: VersionBumpLevel,
        content: Optional[str],
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> RequestSpec:
        body: Dict[str, Any] = {"BumpLevel": bump_level.value}
        if content is not None:
            body["Content"] = content
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"/ecs_/v2/Skills({key})/CreateVersion"),
            json=body,
            headers={**header_folder(folder_key, folder_path)},
        )

    def _update_version_spec(
        self,
        *,
        key: str,
        version_id: str,
        content: Optional[str],
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> RequestSpec:
        body: Dict[str, Any] = {"VersionId": version_id}
        if content is not None:
            body["Content"] = content
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"/ecs_/v2/Skills({key})/UpdateVersion"),
            json=body,
            headers={**header_folder(folder_key, folder_path)},
        )

    def _version_action_spec(
        self,
        *,
        key: str,
        action: str,
        version_id: str,
        folder_path: Optional[str],
        folder_key: Optional[str],
    ) -> RequestSpec:
        return RequestSpec(
            method="POST",
            endpoint=Endpoint(f"/ecs_/v2/Skills({key})/{action}"),
            json={"VersionId": version_id},
            headers={**header_folder(folder_key, folder_path)},
        )
