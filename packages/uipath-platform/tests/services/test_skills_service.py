import pytest
from httpx import HTTPStatusError
from pytest_httpx import HTTPXMock

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.skills import (
    Skill,
    SkillsService,
    SkillVersion,
    SkillVersionStatus,
    VersionBumpLevel,
)


@pytest.fixture
def service(
    config: UiPathApiConfig,
    execution_context: UiPathExecutionContext,
    monkeypatch: pytest.MonkeyPatch,
) -> SkillsService:
    monkeypatch.setenv("UIPATH_FOLDER_PATH", "test-folder-path")
    return SkillsService(config=config, execution_context=execution_context)


SKILL_KEY = "11111111-1111-1111-1111-111111111111"
VERSION_ID = "22222222-2222-2222-2222-222222222222"


def _sample_skill_json() -> dict[str, object]:
    return {
        "id": SKILL_KEY,
        "name": "my-skill",
        "description": "A test skill",
        "gracePeriodDays": 30,
        "createdDate": "2026-05-01T00:00:00Z",
        "lastUpdatedDate": "2026-05-01T00:00:00Z",
        "folderKey": "33333333-3333-3333-3333-333333333333",
        "publishedVersion": {
            "id": VERSION_ID,
            "version": "1.0.0",
            "status": SkillVersionStatus.PUBLISHED.value,
            "publishedAt": "2026-05-01T00:00:00Z",
            "createdDate": "2026-05-01T00:00:00Z",
        },
        "currentDraft": None,
        "versions": [],
        "tags": ["alpha"],
    }


def _sample_version_json(
    status: SkillVersionStatus = SkillVersionStatus.PUBLISHED,
) -> dict[str, object]:
    return {
        "id": VERSION_ID,
        "skillId": SKILL_KEY,
        "version": "1.0.0",
        "content": "You are a helpful skill.",
        "status": status.value,
        "publishedAt": "2026-05-01T00:00:00Z",
        "deprecatedAt": None,
        "retiredAt": None,
        "createdDate": "2026-05-01T00:00:00Z",
    }


class TestSkillsService:
    class TestList:
        def test_list(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills?$skip=0&$top=100",
                status_code=200,
                json={"value": [_sample_skill_json()]},
            )
            page = service.list()
            assert len(page.items) == 1
            assert isinstance(page.items[0], Skill)
            assert page.items[0].name == "my-skill"

        @pytest.mark.asyncio
        async def test_list_async(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills?$skip=0&$top=100",
                status_code=200,
                json={"value": [_sample_skill_json()]},
            )
            page = await service.list_async()
            assert len(page.items) == 1
            assert page.items[0].id == SKILL_KEY

        def test_list_with_name_filter_and_include_content(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=(
                    f"{base_url}{org}{tenant}/ecs_/v2/Skills"
                    "?$skip=0&$top=100&includeContent=true"
                    "&$filter=contains(tolower(Name), tolower('my'))"
                ),
                status_code=200,
                json={"value": []},
            )
            page = service.list(name="my", include_content=True)
            assert page.items == []
            assert page.has_more is False

    class TestListAcrossFolders:
        def test_list_across_folders(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills/AllAcrossFolders(includeContent=false)",
                status_code=200,
                json={"value": [_sample_skill_json()]},
            )
            skills = service.list_across_folders()
            assert len(skills) == 1
            assert skills[0].name == "my-skill"

        @pytest.mark.asyncio
        async def test_list_across_folders_async(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills/AllAcrossFolders(includeContent=true)",
                status_code=200,
                json={"value": []},
            )
            skills = await service.list_across_folders_async(include_content=True)
            assert skills == []

    class TestRetrieve:
        def test_retrieve_by_key(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=(
                    f"{base_url}{org}{tenant}/ecs_/v2/Skills"
                    f"?$filter=id eq {SKILL_KEY}&$top=1&includeContent=true"
                ),
                status_code=200,
                json={"value": [_sample_skill_json()]},
            )
            skill = service.retrieve(key=SKILL_KEY)
            assert skill.id == SKILL_KEY
            assert skill.published_version is not None
            assert skill.published_version.version == "1.0.0"

        def test_retrieve_by_name(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=(
                    f"{base_url}{org}{tenant}/ecs_/v2/Skills"
                    "?$filter=name eq 'my-skill'&$top=1&includeContent=true"
                ),
                status_code=200,
                json={"value": [_sample_skill_json()]},
            )
            skill = service.retrieve(name="my-skill")
            assert skill.name == "my-skill"

        def test_retrieve_missing_args_raises(self, service: SkillsService):
            with pytest.raises(ValueError):
                service.retrieve()

        def test_retrieve_by_name_not_found(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=(
                    f"{base_url}{org}{tenant}/ecs_/v2/Skills"
                    "?$filter=name eq 'nope'&$top=1&includeContent=true"
                ),
                status_code=200,
                json={"value": []},
            )
            with pytest.raises(LookupError):
                service.retrieve(name="nope")

        @pytest.mark.asyncio
        async def test_retrieve_by_key_async(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=(
                    f"{base_url}{org}{tenant}/ecs_/v2/Skills"
                    f"?$filter=id eq {SKILL_KEY}&$top=1&includeContent=true"
                ),
                status_code=200,
                json={"value": [_sample_skill_json()]},
            )
            skill = await service.retrieve_async(key=SKILL_KEY)
            assert skill.id == SKILL_KEY

    class TestCreate:
        def test_create(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills/Create",
                method="POST",
                status_code=200,
                json=_sample_skill_json(),
                match_json={
                    "Name": "my-skill",
                    "Description": "A test skill",
                    "Content": "hello",
                    "Version": "0.0.1",
                },
            )
            skill = service.create(
                name="my-skill",
                description="A test skill",
                content="hello",
                version="0.0.1",
            )
            assert skill.name == "my-skill"

        @pytest.mark.asyncio
        async def test_create_async(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills/Create",
                method="POST",
                status_code=200,
                json=_sample_skill_json(),
                match_json={"Name": "my-skill"},
            )
            skill = await service.create_async(name="my-skill")
            assert skill.name == "my-skill"

    class TestUpdate:
        def test_update(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills({SKILL_KEY})",
                method="PATCH",
                status_code=200,
                json=_sample_skill_json(),
                match_json={"Description": "updated"},
            )
            skill = service.update(key=SKILL_KEY, description="updated")
            assert skill.id == SKILL_KEY

    class TestDelete:
        def test_delete(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills({SKILL_KEY})",
                method="DELETE",
                status_code=204,
            )
            service.delete(key=SKILL_KEY)

        @pytest.mark.asyncio
        async def test_delete_async(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills({SKILL_KEY})",
                method="DELETE",
                status_code=204,
            )
            await service.delete_async(key=SKILL_KEY)

    class TestVersions:
        def test_get_draft(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills({SKILL_KEY})/Draft",
                status_code=200,
                json=_sample_version_json(SkillVersionStatus.DRAFT),
            )
            version = service.get_draft(key=SKILL_KEY)
            assert isinstance(version, SkillVersion)
            assert version.status == SkillVersionStatus.DRAFT

        def test_get_draft_not_found(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills({SKILL_KEY})/Draft",
                status_code=404,
            )
            with pytest.raises((LookupError, HTTPStatusError)):
                service.get_draft(key=SKILL_KEY)

        def test_list_versions_no_filter(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills({SKILL_KEY})/ListVersions()",
                status_code=200,
                json={"value": [_sample_version_json()]},
            )
            versions = service.list_versions(key=SKILL_KEY)
            assert len(versions) == 1

        def test_list_versions_with_filter(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills({SKILL_KEY})/ListVersions(status='Published')",
                status_code=200,
                json={"value": [_sample_version_json()]},
            )
            versions = service.list_versions(
                key=SKILL_KEY, status=SkillVersionStatus.PUBLISHED
            )
            assert versions[0].status == SkillVersionStatus.PUBLISHED

        def test_get_version(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills({SKILL_KEY})/GetVersion(versionId={VERSION_ID})",
                status_code=200,
                json=_sample_version_json(),
            )
            version = service.get_version(key=SKILL_KEY, version_id=VERSION_ID)
            assert version.id == VERSION_ID
            assert version.content == "You are a helpful skill."

        def test_create_version(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills({SKILL_KEY})/CreateVersion",
                method="POST",
                status_code=200,
                json=_sample_version_json(SkillVersionStatus.DRAFT),
                match_json={
                    "BumpLevel": VersionBumpLevel.MINOR.value,
                    "Content": "x",
                },
            )
            v = service.create_version(
                key=SKILL_KEY, bump_level=VersionBumpLevel.MINOR, content="x"
            )
            assert v.id == VERSION_ID

        def test_update_version(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills({SKILL_KEY})/UpdateVersion",
                method="POST",
                status_code=200,
                json=_sample_version_json(SkillVersionStatus.DRAFT),
                match_json={"VersionId": VERSION_ID, "Content": "new"},
            )
            v = service.update_version(
                key=SKILL_KEY, version_id=VERSION_ID, content="new"
            )
            assert v.id == VERSION_ID

        def test_discard_version(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills({SKILL_KEY})/DiscardVersion",
                method="POST",
                status_code=204,
                match_json={"VersionId": VERSION_ID},
            )
            service.discard_version(key=SKILL_KEY, version_id=VERSION_ID)

        @pytest.mark.parametrize(
            "method,action,target_status",
            [
                ("publish_version", "PublishVersion", SkillVersionStatus.PUBLISHED),
                (
                    "deprecate_version",
                    "DeprecateVersion",
                    SkillVersionStatus.DEPRECATED,
                ),
                ("retire_version", "RetireVersion", SkillVersionStatus.RETIRED),
            ],
        )
        def test_version_state_transitions(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
            method: str,
            action: str,
            target_status: SkillVersionStatus,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills({SKILL_KEY})/{action}",
                method="POST",
                status_code=200,
                json=_sample_version_json(target_status),
                match_json={"VersionId": VERSION_ID},
            )
            v = getattr(service, method)(key=SKILL_KEY, version_id=VERSION_ID)
            assert v.status == target_status

        @pytest.mark.asyncio
        async def test_publish_version_async(
            self,
            httpx_mock: HTTPXMock,
            service: SkillsService,
            base_url: str,
            org: str,
            tenant: str,
        ):
            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/ecs_/v2/Skills({SKILL_KEY})/PublishVersion",
                method="POST",
                status_code=200,
                json=_sample_version_json(SkillVersionStatus.PUBLISHED),
                match_json={"VersionId": VERSION_ID},
            )
            v = await service.publish_version_async(
                key=SKILL_KEY, version_id=VERSION_ID
            )
            assert v.status == SkillVersionStatus.PUBLISHED
