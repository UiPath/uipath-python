import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from click.testing import CliRunner

from uipath._cli import cli
from uipath._cli._bindings._emitter import build_binding, merge_bindings
from uipath._cli._bindings._registry import (
    BINDABLE_RESOURCE_TYPES,
    build_registry,
)
from uipath._cli._bindings._scanner import scan_project, scan_source
from uipath._cli._push._resource_actions import CreateVirtual
from uipath._cli.models.runtime_schema import Bindings
from uipath.platform.common._bindings import (
    ResourceOverwriteParser,
    _resource_overwrites,
    resource_override,
)

SAMPLE_DIR = Path(__file__).parents[2] / "samples" / "resource-overrides"


class _EmptyAsyncIterator:
    """Stands in for resource_catalog pagination that finds nothing."""

    def __init__(self) -> None:
        self.aclose = AsyncMock()

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


def _refs_by_type(result):
    return {ref.resource_type: ref for ref in result.references}


class TestRegistry:
    def test_registry_covers_every_bindable_resource_type(self) -> None:
        registry = build_registry()
        found = {spec.resource_type for spec in registry.values()}
        assert BINDABLE_RESOURCE_TYPES <= found

    def test_registry_maps_known_sdk_methods_to_their_parameters(self) -> None:
        registry = build_registry()

        asset = registry[("assets", "retrieve_async")]
        assert asset.resource_type == "asset"
        assert asset.name_param == "name"
        assert asset.folder_param == "folder_path"
        assert asset.name_index == 0

        task = registry[("tasks", "create_async")]
        assert task.resource_type == "app"
        assert task.name_param == "app_name"
        assert task.folder_param == "app_folder_path"
        assert task.name_index is None

        connection = registry[("connections", "retrieve_async")]
        assert connection.resource_type == "connection"
        assert connection.name_param == "key"
        assert connection.folder_param is None

    def test_registry_matches_the_live_resource_override_decorators(self) -> None:
        """Every bindable SDK method that can actually be overridden is known.

        This is the drift guard: a new @resource_override on a bindable service
        that the scanner does not know about would silently produce incomplete
        bindings. Methods whose declared resource_identifier is absent from
        their signature are excluded — the override can never match them at
        runtime either, so there is nothing to bind.
        """
        import inspect

        from uipath.platform import UiPath

        registry = build_registry()
        missing = []
        for service_attr, service_cls in _iter_services(UiPath):
            for method_name, func in vars(service_cls).items():
                meta = _binding_metadata(func)
                if meta is None:
                    continue
                if meta["resource_type"] not in BINDABLE_RESOURCE_TYPES:
                    continue
                if (
                    meta["resource_identifier"]
                    not in inspect.signature(func).parameters
                ):
                    continue
                if (service_attr, method_name) not in registry:
                    missing.append(f"{service_attr}.{method_name}")
        assert missing == []

    def test_activity_name_is_the_async_variant(self) -> None:
        registry = build_registry()
        assert registry[("assets", "retrieve")].activity_name == "retrieve_async"
        assert registry[("processes", "invoke")].activity_name == "invoke_async"


class TestScanner:
    def test_recovers_every_resource_type_from_the_sample_agent(self) -> None:
        result = scan_project(SAMPLE_DIR, build_registry())
        assert _refs_by_type(result).keys() == BINDABLE_RESOURCE_TYPES
        assert result.skipped == []

    def test_reproduces_the_hand_written_sample_bindings_file(self) -> None:
        """The checked-in sample bindings.json is the golden output."""
        expected = json.loads((SAMPLE_DIR / "bindings.json").read_text())
        result = scan_project(SAMPLE_DIR, build_registry())
        generated, _ = merge_bindings(None, result.references)

        produced = generated.model_dump(by_alias=True, exclude_none=True)
        by_key = {(r["resource"], r["key"]): r for r in produced["resources"]}
        for entry in expected["resources"]:
            assert by_key[(entry["resource"], entry["key"])] == entry
        assert produced["version"] == expected["version"]
        assert len(produced["resources"]) == len(expected["resources"])

    def test_folds_module_level_string_constants(self) -> None:
        source = (
            "CONNECTION = 'outlook-key'\n"
            "async def run(sdk):\n"
            "    await sdk.connections.retrieve_async(CONNECTION)\n"
        )
        result = scan_source(source, "graph.py", build_registry())
        ref = _refs_by_type(result)["connection"]
        assert ref.name == "outlook-key"
        assert ref.name_is_expression is False

    def test_does_not_fold_constants_reassigned_in_the_module(self) -> None:
        source = (
            "CONNECTION = 'first'\n"
            "CONNECTION = 'second'\n"
            "async def run(sdk):\n"
            "    await sdk.connections.retrieve_async(CONNECTION)\n"
        )
        result = scan_source(source, "graph.py", build_registry())
        ref = _refs_by_type(result)["connection"]
        assert ref.name == "CONNECTION"
        assert ref.name_is_expression is True

    def test_does_not_fold_constants_changed_by_augmented_assignment(self) -> None:
        """`X += ...` changes the value the call actually receives."""
        source = (
            "CONNECTION = 'first'\n"
            "CONNECTION += '-suffix'\n"
            "async def run(sdk):\n"
            "    await sdk.connections.retrieve_async(CONNECTION)\n"
        )
        result = scan_source(source, "graph.py", build_registry())
        ref = _refs_by_type(result)["connection"]
        assert ref.name == "CONNECTION"
        assert ref.name_is_expression is True

    def test_does_not_fold_constants_reassigned_inside_a_branch(self) -> None:
        """A nested rebind is still a rebind, even though it is not top level."""
        source = (
            "NAME = 'a'\n"
            "if SOMETHING:\n"
            "    NAME = 'b'\n"
            "async def run(sdk):\n"
            "    await sdk.assets.retrieve_async(NAME, folder_path='F')\n"
        )
        result = scan_source(source, "graph.py", build_registry())
        ref = _refs_by_type(result)["asset"]
        assert ref.name == "NAME"
        assert ref.name_is_expression is True

    def test_resolves_a_positionally_passed_folder(self) -> None:
        """context_grounding.retrieve_async takes folder_path at position 2."""
        registry = build_registry()
        assert registry[("context_grounding", "retrieve_async")].folder_index == 2

        source = (
            "async def run(sdk):\n"
            "    await sdk.context_grounding.retrieve_async('Idx', None, 'Policies')\n"
        )
        result = scan_source(source, "main.py", registry)
        ref = _refs_by_type(result)["index"]
        assert ref.name == "Idx"
        assert ref.folder_path == "Policies"
        assert ref.folder_is_expression is False

        from uipath._cli._bindings._emitter import binding_key

        assert binding_key(ref) == "Idx.Policies"

    def test_marks_non_literal_arguments_as_expressions(self) -> None:
        source = (
            "async def run(sdk, state):\n"
            "    await sdk.context_grounding.add_to_index_async(\n"
            "        name=state.index_name, folder_path=state.index_folder_path\n"
            "    )\n"
        )
        result = scan_source(source, "agent.py", build_registry())
        ref = _refs_by_type(result)["index"]
        assert ref.name == "state.index_name"
        assert ref.name_is_expression is True
        assert ref.folder_path == "state.index_folder_path"
        assert ref.folder_is_expression is True

    def test_skips_calls_whose_resource_name_cannot_be_determined(self) -> None:
        source = (
            "def run(self):\n"
            "    self._sdk.buckets.download(\n"
            "        blob_file_path='a', destination_path='b', **self._bucket_kwargs()\n"
            "    )\n"
        )
        result = scan_source(source, "backend.py", build_registry())
        assert result.references == []
        assert len(result.skipped) == 1
        assert result.skipped[0].resource_type == "bucket"
        assert "backend.py:2" in result.skipped[0].source

    def test_resolves_positional_and_keyword_name_arguments(self) -> None:
        source = (
            "async def run(sdk):\n"
            "    await sdk.assets.retrieve_async('positional', folder_path='F')\n"
            "    await sdk.processes.invoke_async(name='keyword', folder_path='F')\n"
        )
        result = scan_source(source, "main.py", build_registry())
        refs = _refs_by_type(result)
        assert refs["asset"].name == "positional"
        assert refs["process"].name == "keyword"

    def test_ignores_unrelated_calls_with_the_same_method_name(self) -> None:
        source = (
            "async def run(repo, sdk):\n"
            "    await repo.customers.retrieve_async('nope')\n"
            "    repo.retrieve_async('nope')\n"
        )
        result = scan_source(source, "main.py", build_registry())
        assert result.references == []
        assert result.skipped == []

    def test_does_not_scan_tests_or_virtualenvs(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text(
            "async def run(sdk):\n    await sdk.assets.retrieve_async('real', folder_path='F')\n"
        )
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_main.py").write_text(
            "async def t(sdk):\n    await sdk.assets.retrieve_async('from_test', folder_path='F')\n"
        )
        (tmp_path / ".venv" / "lib").mkdir(parents=True)
        (tmp_path / ".venv" / "lib" / "dep.py").write_text(
            "async def d(sdk):\n    await sdk.assets.retrieve_async('from_venv', folder_path='F')\n"
        )

        result = scan_project(tmp_path, build_registry())
        assert [ref.name for ref in result.references] == ["real"]

    def test_deduplicates_repeated_references_to_the_same_resource(self) -> None:
        source = (
            "async def run(sdk):\n"
            "    await sdk.assets.retrieve_async('A', folder_path='F')\n"
            "    await sdk.assets.retrieve_async('A', folder_path='F')\n"
        )
        result = scan_source(source, "main.py", build_registry())
        assert len(result.references) == 1


class TestEmitter:
    def test_emitted_entries_satisfy_the_published_json_schema(self) -> None:
        schema = json.loads(
            (Path(__file__).parents[2] / "specs" / "bindings.schema.json").read_text()
        )
        item_schema = schema["properties"]["resources"]["items"]
        allowed_types = set(item_schema["properties"]["resource"]["enum"])
        allowed_value_keys = set()
        for variant in item_schema["properties"]["value"]["oneOf"]:
            allowed_value_keys |= set(variant["properties"])
        required_prop_fields = set(
            schema["definitions"]["propertyDefinition"]["required"]
        )

        result = scan_project(SAMPLE_DIR, build_registry())
        generated, _ = merge_bindings(None, result.references)
        dumped = generated.model_dump(by_alias=True, exclude_none=True)

        assert set(dumped) == {"version", "resources"}
        assert dumped["version"] in schema["properties"]["version"]["enum"]
        for entry in dumped["resources"]:
            assert set(item_schema["required"]) <= set(entry)
            assert set(entry) <= set(item_schema["properties"])
            assert entry["resource"] in allowed_types
            assert set(entry["value"]) <= allowed_value_keys
            for prop in entry["value"].values():
                assert set(prop) == required_prop_fields

    async def test_generated_bindings_survive_the_push_resolver(self) -> None:
        """Every generated entry must yield an action, not an exception.

        `uipath push` reads this file to build solution resources. A binding
        whose shape the resolver rejects (wrong casing on ConnectionId, a
        missing field) raises there rather than in the generator, so drive the
        real resolver over real generated output.
        """
        from uipath._cli._push._resolvers import resolve_bindings
        from uipath.platform.resource_catalog import ResourceType

        result = scan_project(SAMPLE_DIR, build_registry())
        generated, _ = merge_bindings(None, result.references)

        catalog = MagicMock()
        catalog.list_by_type_async.return_value = _EmptyAsyncIterator()
        connections = MagicMock()
        connections.retrieve_async = AsyncMock(
            return_value=SimpleNamespace(
                name="resolved-connection", folder={"path": "Shared"}
            )
        )
        supported = {t.value for t in ResourceType}

        actions = [
            action
            async for action in resolve_bindings(
                generated, catalog, connections, supported
            )
        ]
        assert len(actions) == len(generated.resources)

    async def test_a_binding_without_a_folder_still_resolves(self) -> None:
        """A call with no folder_path is normal — the folder comes from the env."""
        from uipath._cli._push._resolvers import resolve_bindings
        from uipath.platform.resource_catalog import ResourceType

        source = "async def run(sdk):\n    await sdk.assets.retrieve_async('Solo')\n"
        result = scan_source(source, "main.py", build_registry())
        generated, _ = merge_bindings(None, result.references)
        assert generated.resources[0].key == "Solo"

        catalog = MagicMock()
        catalog.list_by_type_async.return_value = _EmptyAsyncIterator()
        actions = [
            action
            async for action in resolve_bindings(
                generated,
                catalog,
                MagicMock(),
                {t.value for t in ResourceType},
            )
        ]
        # Pin the side effect rather than just "an action happened": a folderless
        # binding reaches push as an uncatalogued resource and becomes a virtual
        # placeholder. Changing that is a product decision, not an accident.
        assert len(actions) == 1
        assert isinstance(actions[0], CreateVirtual)
        assert actions[0].request.name == "Solo"

    def test_merge_keeps_hand_edited_entries_untouched(self) -> None:
        existing = Bindings.model_validate(
            {
                "version": "2.0",
                "resources": [
                    {
                        "resource": "asset",
                        "key": "A.F",
                        "value": {
                            "name": {
                                "defaultValue": "A",
                                "isExpression": False,
                                "displayName": "Custom Label",
                            },
                            "folderPath": {
                                "defaultValue": "F",
                                "isExpression": False,
                                "displayName": "Folder Path",
                            },
                        },
                        "metadata": {"BindingsVersion": "2.2", "Hand": "written"},
                    }
                ],
            }
        )
        source = (
            "async def run(sdk):\n"
            "    await sdk.assets.retrieve_async('A', folder_path='F')\n"
            "    await sdk.buckets.retrieve_async(name='B', folder_path='F')\n"
        )
        result = scan_source(source, "main.py", build_registry())
        merged, report = merge_bindings(existing, result.references)

        asset = next(r for r in merged.resources if r.resource == "asset")
        assert asset.value["name"].display_name == "Custom Label"
        assert asset.metadata == {"BindingsVersion": "2.2", "Hand": "written"}
        assert report.added == ["bucket:B.F"]
        assert report.unchanged == ["asset:A.F"]

    def test_merge_never_drops_entries_the_scan_did_not_find(self) -> None:
        existing = Bindings.model_validate(
            {
                "version": "2.0",
                "resources": [
                    {
                        "resource": "index",
                        "key": "state.i.state.f",
                        "value": {
                            "name": {
                                "defaultValue": "state.i",
                                "isExpression": True,
                                "displayName": "Name",
                            },
                            "folderPath": {
                                "defaultValue": "state.f",
                                "isExpression": True,
                                "displayName": "Folder Path",
                            },
                        },
                        "metadata": {"BindingsVersion": "2.2"},
                    }
                ],
            }
        )
        merged, report = merge_bindings(existing, [])
        assert len(merged.resources) == 1
        assert report.preserved == ["index:state.i.state.f"]


class TestRuntimeKeyAgreement:
    """The generated key must be the key the SDK looks up at call time.

    A mismatch here is silent: the override simply never applies and the agent
    runs against its development resource.
    """

    @pytest.mark.parametrize(
        "source",
        [
            "async def run(sdk):\n    await sdk.assets.retrieve_async('A', folder_path='F')\n",
            "async def run(sdk):\n    await sdk.processes.invoke_async(name='P', folder_path='F')\n",
            "async def run(sdk):\n    await sdk.buckets.retrieve_async(name='B', folder_path='F')\n",
            "async def run(sdk):\n    await sdk.context_grounding.retrieve_async(name='I', folder_path='F')\n",
            "async def run(sdk):\n    await sdk.tasks.create_async('t', app_name='APP', app_folder_path='F')\n",
            "async def run(sdk):\n    await sdk.connections.retrieve_async('C')\n",
        ],
    )
    def test_override_applies_to_the_generated_key(self, source: str) -> None:
        registry = build_registry()
        result = scan_source(source, "main.py", registry)
        ref = result.references[0]
        binding = build_binding(ref)
        spec = next(
            s for s in registry.values() if s.resource_type == ref.resource_type
        )

        probe = _make_probe(spec)
        overwrite_key = f"{ref.resource_type}.{binding.key}"
        # Built through the same parser the runtime uses on the server's
        # response, so the test exercises the production construction path.
        payload: dict[str, Any] = (
            {"connectionId": "NEW_ID", "folderKey": "NEW_FOLDER"}
            if ref.resource_type == "connection"
            else {"name": "NEW_NAME", "folderPath": "NEW_FOLDER"}
        )
        overwrite = ResourceOverwriteParser.parse(overwrite_key, payload)

        call_args: dict[str, Any] = {spec.name_param: ref.name}
        if spec.folder_param:
            call_args[spec.folder_param] = ref.folder_path

        token = _resource_overwrites.set({overwrite_key: overwrite})
        try:
            observed_name, observed_folder = probe(**call_args)
        finally:
            _resource_overwrites.reset(token)

        expected_name = "NEW_ID" if ref.resource_type == "connection" else "NEW_NAME"
        assert observed_name == expected_name
        if spec.folder_param:
            assert observed_folder == "NEW_FOLDER"


class TestCommand:
    def _project(self, body: str) -> None:
        with open("pyproject.toml", "w") as f:
            f.write(
                '[project]\nname = "test-project"\nversion = "0.1.0"\n'
                'description = "Test"\nauthors = [{name = "Test"}]\n'
                'requires-python = ">=3.11"\n'
            )
        with open("main.py", "w") as f:
            f.write(body)

    def test_generate_writes_bindings_for_discovered_resources(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._project(
                "async def run(sdk):\n"
                "    await sdk.assets.retrieve_async('MyAsset', folder_path='Shared')\n"
            )
            result = runner.invoke(cli, ["bindings", "generate"], env={})
            assert result.exit_code == 0, result.output

            data = json.loads(Path("bindings.json").read_text())
            assert data["version"] == "2.0"
            assert len(data["resources"]) == 1
            assert data["resources"][0]["key"] == "MyAsset.Shared"

    def test_generate_reports_what_it_could_not_resolve(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._project(
                "def run(self):\n"
                "    self._sdk.buckets.download(blob_file_path='a', **self._kw())\n"
            )
            result = runner.invoke(cli, ["bindings", "generate"], env={})
            assert result.exit_code == 0, result.output
            assert "main.py:2" in result.output
            assert "bucket" in result.output

    def test_dry_run_does_not_write_the_file(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._project(
                "async def run(sdk):\n"
                "    await sdk.assets.retrieve_async('MyAsset', folder_path='Shared')\n"
            )
            result = runner.invoke(cli, ["bindings", "generate", "--dry-run"], env={})
            assert result.exit_code == 0, result.output
            assert not os.path.exists("bindings.json")

    def test_check_fails_when_the_file_is_out_of_date(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._project(
                "async def run(sdk):\n"
                "    await sdk.assets.retrieve_async('MyAsset', folder_path='Shared')\n"
            )
            Path("bindings.json").write_text('{"version": "2.0", "resources": []}')

            result = runner.invoke(cli, ["bindings", "generate", "--check"], env={})
            assert result.exit_code == 1
            assert json.loads(Path("bindings.json").read_text())["resources"] == []

    def test_check_passes_when_the_file_is_up_to_date(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._project(
                "async def run(sdk):\n"
                "    await sdk.assets.retrieve_async('MyAsset', folder_path='Shared')\n"
            )
            assert runner.invoke(cli, ["bindings", "generate"], env={}).exit_code == 0
            result = runner.invoke(cli, ["bindings", "generate", "--check"], env={})
            assert result.exit_code == 0, result.output

    def test_rerunning_is_idempotent(self, runner: CliRunner, temp_dir: str) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._project(
                "async def run(sdk):\n"
                "    await sdk.assets.retrieve_async('MyAsset', folder_path='Shared')\n"
            )
            runner.invoke(cli, ["bindings", "generate"], env={})
            first = Path("bindings.json").read_text()
            runner.invoke(cli, ["bindings", "generate"], env={})
            assert Path("bindings.json").read_text() == first


def _iter_services(uipath_cls):
    import typing

    for attr, descriptor in vars(uipath_cls).items():
        fget = getattr(descriptor, "fget", None) or getattr(descriptor, "func", None)
        if fget is None:
            continue
        try:
            hints = typing.get_type_hints(fget)
        except Exception:
            continue
        service_cls = hints.get("return")
        if isinstance(service_cls, type):
            yield attr, service_cls


def _binding_metadata(func):
    target = getattr(func, "__func__", func)
    meta = getattr(target, "__uipath_binding__", None)
    if meta is not None:
        return meta
    closure = getattr(target, "__closure__", None)
    code = getattr(target, "__code__", None)
    if not closure or code is None:
        return None
    cells = dict(zip(code.co_freevars, closure, strict=True))
    process_args = cells.get("process_args")
    if process_args is None:
        return None
    inner = process_args.cell_contents
    inner_cells = dict(
        zip(inner.__code__.co_freevars, inner.__closure__ or (), strict=True)
    )
    if "resource_type" not in inner_cells:
        return None
    return {
        "resource_type": inner_cells["resource_type"].cell_contents,
        "resource_identifier": inner_cells["resource_identifier"].cell_contents,
        "folder_identifier": inner_cells["folder_identifier"].cell_contents,
    }


def _make_probe(spec):
    params = [f"{spec.name_param}=None"]
    if spec.folder_param:
        params.append(f"{spec.folder_param}=None")
    folder_expr = spec.folder_param if spec.folder_param else "None"
    namespace: dict[str, Any] = {}
    exec(
        f"def probe({', '.join(params)}):\n"
        f"    return ({spec.name_param}, {folder_expr})\n",
        namespace,
    )
    return resource_override(
        resource_type=spec.resource_type,
        resource_identifier=spec.name_param,
        folder_identifier=spec.folder_param or "folder_path",
    )(namespace["probe"])


class TestInitInferBindings:
    def _project(self, body: str) -> None:
        with open("pyproject.toml", "w") as f:
            f.write(
                '[project]\nname = "test-project"\nversion = "0.1.0"\n'
                'description = "Test"\nauthors = [{name = "Test"}]\n'
                'requires-python = ">=3.11"\n'
            )
        with open("main.py", "w") as f:
            f.write(body)

    _AGENT = (
        "async def run(sdk):\n"
        "    await sdk.assets.retrieve_async('MyAsset', folder_path='Shared')\n"
    )

    def test_init_leaves_bindings_empty_without_the_flag(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Discovery stays opt-in: plain `init` must not invent bindings."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._project(self._AGENT)
            result = runner.invoke(cli, ["init"], env={})
            assert result.exit_code == 0, result.output
            assert json.loads(Path("bindings.json").read_text())["resources"] == []

    def test_init_infer_bindings_records_discovered_resources(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._project(self._AGENT)
            result = runner.invoke(cli, ["init", "--infer-bindings"], env={})
            assert result.exit_code == 0, result.output

            resources = json.loads(Path("bindings.json").read_text())["resources"]
            assert [r["key"] for r in resources] == ["MyAsset.Shared"]

    def test_init_infer_bindings_merges_into_an_existing_file(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            self._project(self._AGENT)
            Path("bindings.json").write_text(
                json.dumps(
                    {
                        "version": "2.0",
                        "resources": [
                            {
                                "resource": "connection",
                                "key": "kept",
                                "value": {
                                    "ConnectionId": {
                                        "defaultValue": "kept",
                                        "isExpression": False,
                                        "displayName": "Connection",
                                    }
                                },
                                "metadata": {"BindingsVersion": "2.2"},
                            }
                        ],
                    }
                )
            )
            result = runner.invoke(cli, ["init", "--infer-bindings"], env={})
            assert result.exit_code == 0, result.output

            keys = {
                r["key"]
                for r in json.loads(Path("bindings.json").read_text())["resources"]
            }
            assert keys == {"kept", "MyAsset.Shared"}
