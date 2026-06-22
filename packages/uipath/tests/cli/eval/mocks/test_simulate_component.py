"""Tests for SimulateComponentMocker and SimulateComponentService."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pytest_httpx import HTTPXMock

from uipath.eval.mocks._mock_context import is_tool_simulated
from uipath.eval.mocks._mock_runtime import (
    clear_execution_context,
    set_execution_context,
)
from uipath.eval.mocks._mocker import (
    UiPathMockResponseGenerationError,
)
from uipath.eval.mocks._simulate_component_mocker import SimulateComponentMocker
from uipath.eval.mocks._simulate_component_service import (
    SimulateComponentService,
    _create_simulate_component_service,
)
from uipath.eval.mocks._types import (
    ComponentSimulationConfig,
    MockingContext,
    SimulationStrategy,
    UnknownMockingStrategy,
)
from uipath.eval.mocks.mockable import mockable

_mock_span_collector = MagicMock()

BASE_URL = "https://example.com"
_SIMULATE_PATH = (
    "uipath.eval.mocks._simulate_component_mocker._create_simulate_component_service"
)


def _make_context(
    component_id: str = "my_tool",
    strategy: SimulationStrategy = SimulationStrategy.LLM,
    instruction: str = "simulate it",
    workload_id: str = "wl-123",
) -> MockingContext:
    return MockingContext(
        strategy=None,
        name="test-run",
        inputs={"q": "hello"},
        workload_id=workload_id,
        components=[
            ComponentSimulationConfig(
                component_id=component_id,
                component_type="tool",
                simulation_strategy=strategy,
                simulation_instruction=instruction,
            )
        ],
    )


def _make_service_mock(result: dict[str, Any]) -> MagicMock:
    svc = MagicMock()
    svc.simulate = AsyncMock(return_value=result)
    return svc


# ---------------------------------------------------------------------------
# is_tool_simulated with components format
# ---------------------------------------------------------------------------


class TestIsToolSimulatedWithComponents:
    def setup_method(self):
        clear_execution_context()

    def teardown_method(self):
        clear_execution_context()

    def test_returns_true_for_listed_component(self):
        set_execution_context(_make_context("search_tool"), _mock_span_collector, "x")
        assert is_tool_simulated("search_tool") is True

    def test_returns_false_for_unlisted_component(self):
        set_execution_context(_make_context("search_tool"), _mock_span_collector, "x")
        assert is_tool_simulated("other_tool") is False

    def test_underscore_space_normalisation(self):
        ctx = MockingContext(
            strategy=None,
            name="run",
            inputs={},
            components=[
                ComponentSimulationConfig(
                    component_id="web search",
                    simulation_strategy=SimulationStrategy.LLM,
                )
            ],
        )
        set_execution_context(ctx, _mock_span_collector, "x")
        assert is_tool_simulated("web_search") is True

    def test_returns_false_when_components_list_is_empty(self):
        ctx = MockingContext(strategy=None, name="run", inputs={}, components=[])
        set_execution_context(ctx, _mock_span_collector, "x")
        # components is set but empty — MockerFactory won't create a mocker (components is not None)
        # is_tool_simulated: ctx.components is not None → iterates empty list → False
        assert is_tool_simulated("any_tool") is False


# ---------------------------------------------------------------------------
# SimulateComponentMocker._find_component
# ---------------------------------------------------------------------------


class TestFindComponent:
    def test_finds_by_exact_id(self):
        mocker = SimulateComponentMocker(_make_context("my_tool"))
        assert mocker._find_component("my_tool") is not None

    def test_finds_by_underscore_to_space_normalisation(self):
        ctx = MockingContext(
            strategy=None,
            name="run",
            inputs={},
            components=[
                ComponentSimulationConfig(
                    component_id="web search",
                    simulation_strategy=SimulationStrategy.LLM,
                )
            ],
        )
        mocker = SimulateComponentMocker(ctx)
        assert mocker._find_component("web_search") is not None

    def test_returns_none_for_unknown_tool(self):
        mocker = SimulateComponentMocker(_make_context("my_tool"))
        assert mocker._find_component("unknown") is None


# ---------------------------------------------------------------------------
# SimulateComponentMocker.response — success path
# ---------------------------------------------------------------------------


class TestSimulateComponentMockerResponse:
    @pytest.mark.asyncio
    async def test_returns_simulated_output_on_status_1(self):
        ctx = _make_context("my_tool")
        svc_mock = _make_service_mock({"status": 1, "simulatedOutput": "hello"})

        @mockable()
        async def my_tool() -> str:
            raise NotImplementedError()

        set_execution_context(ctx, _mock_span_collector, "exec-1")
        with patch(_SIMULATE_PATH, return_value=svc_mock):
            result = await my_tool()

        assert result == "hello"
        clear_execution_context()

    @pytest.mark.asyncio
    async def test_raises_generation_error_on_non_1_status(self):
        ctx = _make_context("my_tool")
        svc_mock = _make_service_mock(
            {"status": 2, "error": {"message": "LLM timeout"}}
        )

        @mockable()
        async def my_tool() -> str:
            raise NotImplementedError()

        set_execution_context(ctx, _mock_span_collector, "exec-2")
        with patch(_SIMULATE_PATH, return_value=svc_mock):
            with pytest.raises(UiPathMockResponseGenerationError, match="LLM timeout"):
                await my_tool()

        clear_execution_context()

    @pytest.mark.asyncio
    async def test_raises_generic_error_when_error_message_missing(self):
        ctx = _make_context("my_tool")
        svc_mock = _make_service_mock({"status": 0, "error": {}})

        @mockable()
        async def my_tool() -> str:
            raise NotImplementedError()

        set_execution_context(ctx, _mock_span_collector, "exec-3")
        with patch(_SIMULATE_PATH, return_value=svc_mock):
            with pytest.raises(
                UiPathMockResponseGenerationError, match="Simulation failed"
            ):
                await my_tool()

        clear_execution_context()

    @pytest.mark.asyncio
    async def test_raises_generation_error_when_api_throws(self):
        ctx = _make_context("my_tool")
        svc_mock = MagicMock()
        svc_mock.simulate = AsyncMock(side_effect=RuntimeError("network error"))

        @mockable()
        async def my_tool() -> str:
            raise NotImplementedError()

        set_execution_context(ctx, _mock_span_collector, "exec-4")
        with patch(_SIMULATE_PATH, return_value=svc_mock):
            with pytest.raises(
                UiPathMockResponseGenerationError,
                match="simulate-component API call failed",
            ):
                await my_tool()

        clear_execution_context()

    @pytest.mark.asyncio
    async def test_raises_no_mock_found_for_unconfigured_tool(self):
        ctx = _make_context("my_tool")

        @mockable()
        async def other_tool() -> str:
            raise NotImplementedError()

        set_execution_context(ctx, _mock_span_collector, "exec-5")
        # other_tool is not in components → falls through to real function
        with pytest.raises(NotImplementedError):
            await other_tool()

        clear_execution_context()


# ---------------------------------------------------------------------------
# Payload construction
# ---------------------------------------------------------------------------


class TestPayloadConstruction:
    @pytest.mark.asyncio
    async def test_payload_fields_sent_to_service(self):
        ctx = _make_context("my_tool", instruction="Do something", workload_id="wl-99")
        captured: list[dict[str, Any]] = []

        async def _capture(payload, **kwargs):
            captured.append(payload)
            return {"status": 1, "simulatedOutput": "ok"}

        svc_mock = MagicMock()
        svc_mock.simulate = _capture

        @mockable()
        async def my_tool(x: int) -> str:
            raise NotImplementedError()

        set_execution_context(ctx, _mock_span_collector, "exec-6")
        with patch(_SIMULATE_PATH, return_value=svc_mock):
            await my_tool(x=42)

        assert len(captured) == 1
        p = captured[0]
        assert p["workloadId"] == "wl-99"
        assert p["componentId"] == "my_tool"
        assert p["componentType"] == "tool"
        assert p["simulationInstruction"] == "Do something"
        assert p["simulationStrategy"] == int(SimulationStrategy.LLM)
        assert p["workloadInfo"] == {"name": "test-run", "userInput": {"q": "hello"}}

        clear_execution_context()

    @pytest.mark.asyncio
    async def test_sync_mockable_also_works(self):
        ctx = _make_context("sync_tool")
        svc_mock = _make_service_mock({"status": 1, "simulatedOutput": 42})

        @mockable()
        def sync_tool() -> int:
            raise NotImplementedError()

        set_execution_context(ctx, _mock_span_collector, "exec-7")
        with patch(_SIMULATE_PATH, return_value=svc_mock):
            result = sync_tool()

        assert result == 42
        clear_execution_context()

    @pytest.mark.asyncio
    async def test_payload_uses_configured_component_id_not_invoked_name(self):
        """componentId in payload must be the configured ID, not the normalised call name."""
        ctx = MockingContext(
            strategy=None,
            name="run",
            inputs={},
            components=[
                ComponentSimulationConfig(
                    component_id="web search",
                    simulation_strategy=SimulationStrategy.LLM,
                )
            ],
        )
        captured: list[dict[str, Any]] = []

        async def _capture(payload, **kwargs):
            captured.append(payload)
            return {"status": 1, "simulatedOutput": "ok"}

        svc_mock = MagicMock()
        svc_mock.simulate = _capture

        @mockable()
        async def web_search() -> str:
            raise NotImplementedError()

        set_execution_context(ctx, _mock_span_collector, "exec-8")
        with patch(_SIMULATE_PATH, return_value=svc_mock):
            await web_search()

        assert captured[0]["componentId"] == "web search"
        clear_execution_context()


# ---------------------------------------------------------------------------
# _build_execution_history — uncovered branch (no context vars set)
# ---------------------------------------------------------------------------


class TestBuildExecutionHistory:
    def test_returns_none_when_context_vars_not_set(self):
        clear_execution_context()
        mocker = SimulateComponentMocker(_make_context())
        assert mocker._build_execution_history() is None

    def test_returns_none_when_spans_empty(self):
        from uipath.eval._execution_context import (
            execution_id_context,
            span_collector_context,
        )

        span_collector = MagicMock()
        span_collector.get_spans = MagicMock(return_value=[])
        span_collector_context.set(span_collector)
        execution_id_context.set("exec-id")

        mocker = SimulateComponentMocker(_make_context())
        assert mocker._build_execution_history() is None

        clear_execution_context()


# ---------------------------------------------------------------------------
# MockerFactory — unknown strategy raises ValueError
# ---------------------------------------------------------------------------


class TestMockerFactory:
    def test_raises_for_unknown_strategy(self):
        from uipath.eval.mocks._mocker_factory import MockerFactory

        ctx = MockingContext(
            strategy=UnknownMockingStrategy(type="future_strategy"),
            name="test",
            inputs={},
            components=None,
        )
        with pytest.raises(ValueError, match="Unknown mocking strategy"):
            MockerFactory.create(ctx)

    def test_raises_for_none_strategy_and_no_components(self):
        from uipath.eval.mocks._mocker_factory import MockerFactory

        ctx = MockingContext(strategy=None, name="test", inputs={}, components=None)
        with pytest.raises(ValueError, match="Unknown mocking strategy"):
            MockerFactory.create(ctx)


# ---------------------------------------------------------------------------
# is_tool_simulated — unknown strategy falls through to False
# ---------------------------------------------------------------------------


class TestIsToolSimulatedUnknownStrategy:
    def setup_method(self):
        clear_execution_context()

    def teardown_method(self):
        clear_execution_context()

    def test_returns_false_for_unknown_strategy(self):

        ctx = MockingContext(
            strategy=UnknownMockingStrategy(type="future_strategy"),
            name="test",
            inputs={},
            components=None,
        )
        set_execution_context(ctx, _mock_span_collector, "x")
        assert is_tool_simulated("any_tool") is False


# ---------------------------------------------------------------------------
# SimulateComponentService — actual HTTP call
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_simulate_component_service_http_call(
    httpx_mock: HTTPXMock, monkeypatch: MonkeyPatch
):
    monkeypatch.setenv("UIPATH_URL", "https://example.com/myorg/mytenant")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "token")

    httpx_mock.add_response(
        url="https://example.com/myorg/mytenant/agentsruntime_/api/execution/simulations/simulate-component",
        method="POST",
        json={"status": 1, "simulatedOutput": "result"},
    )

    service = _create_simulate_component_service()
    assert isinstance(service, SimulateComponentService)

    result = await service.simulate({"componentId": "my_tool"})
    assert result == {"status": 1, "simulatedOutput": "result"}


@pytest.mark.asyncio
@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_simulate_component_service_no_headers(
    httpx_mock: HTTPXMock, monkeypatch: MonkeyPatch
):
    monkeypatch.setenv("UIPATH_URL", "https://example.com/myorg/mytenant")
    monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "token")

    httpx_mock.add_response(
        url="https://example.com/myorg/mytenant/agentsruntime_/api/execution/simulations/simulate-component",
        method="POST",
        json={"status": 0, "error": {"message": "boom"}},
    )

    service = _create_simulate_component_service()
    result = await service.simulate({"componentId": "my_tool"})
    assert result["status"] == 0
