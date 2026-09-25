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
    _binding_metadata,
    _iter_service_classes,
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


def _hand_written(
    resource: str,
    key: str,
    *,
    display_name: str = "Name",
    is_expression: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """A bindings.json entry as a person would have written it."""
    name, _, folder = key.rpartition(".")
    return {
        "resource": resource,
        "key": key,
        "value": {
            "name": {
                "defaultValue": name,
                "isExpression": is_expression,
                "displayName": display_name,
            },
            "folderPath": {
                "defaultValue": folder,
                "isExpression": is_expression,
                "displayName": "Folder Path",
            },
        },
        "metadata": metadata or {"BindingsVersion": "2.2"},
    }


async def _resolve(bindings):
    """Run the real push resolver against a catalog that finds nothing."""
    from uipath._cli._push._resolvers import resolve_bindings
    from uipath.platform.resource_catalog import ResourceType

    catalog = MagicMock()
    catalog.list_by_type_async.return_value = _EmptyAsyncIterator()
    connections = MagicMock()
    connections.retrieve_async = AsyncMock(
        return_value=SimpleNamespace(name="resolved", folder={"path": "Shared"})
    )
    return [
        action
        async for action in resolve_bindings(
            bindings, catalog, connections, {t.value for t in ResourceType}
        )
    ]


def _refs_by_type(result):
    return {ref.resource_type: ref for ref in result.references}


class TestRegistry:
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

        registry = build_registry()
        missing = []
        for service_attr, service_cls in _iter_service_classes():
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

    @pytest.mark.parametrize(
        "rebind",
        [
            pytest.param("CONNECTION = 'second'", id="reassigned"),
            pytest.param("CONNECTION += '-suffix'", id="augmented"),
            pytest.param("if SOMETHING:\n    CONNECTION = 'other'", id="in-a-branch"),
            pytest.param("def f():\n    CONNECTION = 'local'", id="shadowed-locally"),
        ],
    )
    def test_does_not_fold_a_constant_that_is_rebound(self, rebind: str) -> None:
        """Any second binding means the call site may not see the literal."""
        source = (
            f"CONNECTION = 'first'\n{rebind}\n"
            "async def run(sdk):\n"
            "    await sdk.connections.retrieve_async(CONNECTION)\n"
        )
        result = scan_source(source, "graph.py", build_registry())
        assert result.references == []
        assert len(result.skipped) == 1

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

        from uipath._cli._bindings._emitter import binding_key

        assert binding_key(ref) == "Idx.Policies"

    @pytest.mark.parametrize(
        ("call", "expression"),
        [
            pytest.param(
                "await sdk.context_grounding.retrieve_async(name=state.index_name)",
                "state.index_name",
                id="attribute",
            ),
            # samples/asset-modifier-agent does exactly this; it used to emit a
            # binding keyed on the parameter names.
            pytest.param(
                "await sdk.context_grounding.retrieve_async(name=index_name)",
                "index_name",
                id="parameter",
            ),
            pytest.param(
                "await sdk.context_grounding.retrieve_async(name=f'idx-{state.id}')",
                "idx-",
                id="f-string",
            ),
        ],
    )
    def test_skips_a_name_computed_at_runtime(self, call: str, expression: str) -> None:
        """A python expression is not a resource name, so never emit one."""
        source = f"async def run(sdk, state, index_name):\n    {call}\n"
        result = scan_source(source, "agent.py", build_registry())
        assert result.references == []
        assert len(result.skipped) == 1
        assert expression in result.skipped[0].reason
        assert result.skipped[0].source == "agent.py:2"

    def test_skips_a_literal_name_whose_folder_is_computed(self) -> None:
        """Half a binding is still a binding push would act on."""
        source = (
            "import os\n"
            "async def run(sdk):\n"
            "    await sdk.assets.retrieve_async(\n"
            "        'ApiKey', folder_path=os.getenv('FOLDER')\n"
            "    )\n"
        )
        result = scan_source(source, "agent.py", build_registry())
        assert result.references == []
        assert len(result.skipped) == 1

    def test_a_missing_folder_is_not_an_expression(self) -> None:
        """No folder argument at all is fine; the environment supplies it."""
        source = "async def run(sdk):\n    await sdk.assets.retrieve_async('Solo')\n"
        result = scan_source(source, "agent.py", build_registry())
        assert [r.name for r in result.references] == ["Solo"]
        assert result.skipped == []

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


class TestInterruptModels:
    """Resources reached through `interrupt(...)`, not a direct SDK call.

    LangGraph agents invoke processes and create actions by constructing an
    interrupt model; the runtime then calls the decorated SDK method. The call
    site in user code is a constructor, so the decorator registry alone cannot
    see it.
    """

    @pytest.mark.parametrize(
        ("imports", "call", "resource_type", "name"),
        [
            pytest.param(
                "from uipath.platform.common.interrupt_models import InvokeProcess",
                "InvokeProcess(name='child-agent', process_folder_path='Shared')",
                "process",
                "child-agent",
                id="invoke-process",
            ),
            pytest.param(
                "from uipath.platform.common.interrupt_models import CreateTask",
                "CreateTask(title='Review', app_name='escalation_app',"
                " app_folder_path='Shared')",
                "app",
                "escalation_app",
                id="create-task",
            ),
            pytest.param(
                "from uipath.platform.common import interrupt_models",
                "interrupt_models.CreateEscalation(title='t', app_name='approval',"
                " app_folder_path='Ops')",
                "app",
                "approval",
                id="module-qualified",
            ),
        ],
    )
    def test_a_model_constructor_is_discovered(
        self, imports: str, call: str, resource_type: str, name: str
    ) -> None:
        source = f"{imports}\ndef node(state):\n    return interrupt({call})\n"
        result = scan_source(source, "graph.py", build_registry())
        ref = _refs_by_type(result)[resource_type]
        assert ref.name == name
        assert ref.folder_path in {"Shared", "Ops"}

    def test_deep_rag_binds_the_index_not_the_task_name(self) -> None:
        """`name` is the task's own name; `index_name` is the resource."""
        source = (
            "from uipath.platform.common.interrupt_models import CreateDeepRag\n"
            "def node(state):\n"
            "    return interrupt(CreateDeepRag(\n"
            "        name='my-research-task',\n"
            "        index_name='ExpensePolicy',\n"
            "        index_folder_path='HR',\n"
            "        prompt='summarise',\n"
            "    ))\n"
        )
        result = scan_source(source, "graph.py", build_registry())
        ref = _refs_by_type(result)["index"]
        assert ref.name == "ExpensePolicy"
        assert ref.folder_path == "HR"

    def test_a_same_named_class_from_elsewhere_is_ignored(self) -> None:
        """Only constructors imported from uipath count."""
        source = (
            "from myapp.jobs import InvokeProcess\n"
            "def node(state):\n"
            "    return InvokeProcess(name='not-ours', process_folder_path='X')\n"
        )
        result = scan_source(source, "graph.py", build_registry())
        assert result.references == []
        assert result.skipped == []

    def test_a_wait_model_binds_nothing(self) -> None:
        """Wait models reference an already-created job by key."""
        source = (
            "from uipath.platform.common.interrupt_models import WaitJob\n"
            "def node(state):\n"
            "    return interrupt(WaitJob(job=state.job, process_folder_path='Shared'))\n"
        )
        result = scan_source(source, "graph.py", build_registry())
        assert result.references == []

    def test_every_interrupt_model_is_classified(self) -> None:
        """A new interrupt model must be mapped or explicitly excluded.

        Same drift guard as the decorator registry: adding a model that names a
        resource should fail here rather than silently produce no binding.
        """
        from pydantic import BaseModel

        from uipath._cli._bindings._interrupts import (
            INTERRUPT_SPECS,
            NON_BINDING_INTERRUPT_MODELS,
        )
        from uipath.platform.common import interrupt_models

        declared = set(INTERRUPT_SPECS) | set(NON_BINDING_INTERRUPT_MODELS)
        live = {
            name
            for name, obj in vars(interrupt_models).items()
            if isinstance(obj, type)
            and issubclass(obj, BaseModel)
            and obj.__module__ == interrupt_models.__name__
        }
        assert live - declared == set()


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
        """`uipath push` reads this file. A binding whose shape the resolver
        rejects — wrong casing on ConnectionId, a missing field — raises there
        rather than in the generator, so drive the real resolver over real
        generated output.
        """
        result = scan_project(SAMPLE_DIR, build_registry())
        generated, _ = merge_bindings(None, result.references)
        actions = await _resolve(generated)
        assert len(actions) == len(generated.resources)

    async def test_a_binding_without_a_folder_becomes_a_virtual_resource(
        self,
    ) -> None:
        """A call with no folder_path is normal; the environment supplies one.

        Pin the side effect rather than just "an action happened": such a
        binding reaches push as an uncatalogued resource and becomes a
        placeholder. Changing that is a product decision, not an accident.
        """
        source = "async def run(sdk):\n    await sdk.assets.retrieve_async('Solo')\n"
        result = scan_source(source, "main.py", build_registry())
        generated, _ = merge_bindings(None, result.references)
        assert generated.resources[0].key == "Solo"

        actions = await _resolve(generated)
        assert len(actions) == 1
        assert isinstance(actions[0], CreateVirtual)
        assert actions[0].request.name == "Solo"

    def test_merge_leaves_what_it_did_not_generate_alone(self) -> None:
        """Existing entries carry display names, metadata and expressions a
        scan cannot reproduce, so a known key is never rewritten and an entry
        the scan did not find is never pruned.
        """
        existing = Bindings.model_validate(
            {
                "version": "2.0",
                "resources": [
                    _hand_written(
                        "asset",
                        "A.F",
                        display_name="Custom Label",
                        metadata={"BindingsVersion": "2.2", "Hand": "written"},
                    ),
                    _hand_written("index", "state.i.state.f", is_expression=True),
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
        assert report.unchanged == ["asset:A.F"]
        assert report.added == ["bucket:B.F"]

        index = next(r for r in merged.resources if r.resource == "index")
        assert index.value["name"].is_expression is True
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


def _write_project(body: str) -> None:
    """A minimal project in the cwd, for the CLI tests."""
    Path("pyproject.toml").write_text(
        '[project]\nname = "test-project"\nversion = "0.1.0"\n'
        'description = "Test"\nauthors = [{name = "Test"}]\n'
        'requires-python = ">=3.11"\n'
    )
    Path("main.py").write_text(body)


_AGENT = (
    "async def run(sdk):\n"
    "    await sdk.assets.retrieve_async('MyAsset', folder_path='Shared')\n"
)


class TestCommand:
    def test_generate_writes_bindings_for_discovered_resources(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            _write_project(_AGENT)
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
            _write_project(
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
            _write_project(_AGENT)
            result = runner.invoke(cli, ["bindings", "generate", "--dry-run"], env={})
            assert result.exit_code == 0, result.output
            assert not os.path.exists("bindings.json")

    def test_check_fails_when_the_file_is_out_of_date(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            _write_project(_AGENT)
            Path("bindings.json").write_text('{"version": "2.0", "resources": []}')

            result = runner.invoke(cli, ["bindings", "generate", "--check"], env={})
            assert result.exit_code == 1
            assert json.loads(Path("bindings.json").read_text())["resources"] == []

    def test_check_passes_when_the_file_is_up_to_date(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            _write_project(_AGENT)
            assert runner.invoke(cli, ["bindings", "generate"], env={}).exit_code == 0
            result = runner.invoke(cli, ["bindings", "generate", "--check"], env={})
            assert result.exit_code == 0, result.output

    def test_rerunning_is_idempotent(self, runner: CliRunner, temp_dir: str) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            _write_project(_AGENT)
            runner.invoke(cli, ["bindings", "generate"], env={})
            first = Path("bindings.json").read_text()
            runner.invoke(cli, ["bindings", "generate"], env={})
            assert Path("bindings.json").read_text() == first


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
    def test_init_leaves_bindings_empty_without_the_flag(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        """Discovery stays opt-in: plain `init` must not invent bindings."""
        with runner.isolated_filesystem(temp_dir=temp_dir):
            _write_project(_AGENT)
            result = runner.invoke(cli, ["init"], env={})
            assert result.exit_code == 0, result.output
            assert json.loads(Path("bindings.json").read_text())["resources"] == []

    def test_init_infer_bindings_records_discovered_resources(
        self, runner: CliRunner, temp_dir: str
    ) -> None:
        with runner.isolated_filesystem(temp_dir=temp_dir):
            _write_project(_AGENT)
            result = runner.invoke(cli, ["init", "--infer-bindings"], env={})
            assert result.exit_code == 0, result.output

            resources = json.loads(Path("bindings.json").read_text())["resources"]
            assert [r["key"] for r in resources] == ["MyAsset.Shared"]
