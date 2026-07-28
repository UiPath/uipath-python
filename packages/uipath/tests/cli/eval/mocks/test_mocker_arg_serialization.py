"""Tool arguments must survive simulation regardless of their Python type.

A simulated tool call is serialized twice: once by ``LLMMocker`` to build the
simulation prompt, and once by ``SimulateComponentService`` to POST the payload.
Tool ``args_schema`` models may type a field as any Python type (``uuid.UUID``,
``datetime``, ``Enum``, ...), and LangChain hands the tool the *validated*
value, so both paths receive objects the stdlib JSON encoder rejects.
"""

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pytest_httpx import HTTPXMock

from uipath.eval.mocks._mock_runtime import (
    clear_execution_context,
    set_execution_context,
)
from uipath.eval.mocks._simulate_component_service import (
    _create_simulate_component_service,
)
from uipath.eval.mocks._types import (
    ComponentSimulationConfig,
    LLMMockingStrategy,
    MockingContext,
    SimulationStrategy,
    ToolSimulation,
)
from uipath.eval.mocks.mockable import mockable

_mock_span_collector = MagicMock()

_ATTACHMENT_ID = uuid.UUID("9b702dc7-4988-4fc0-ba81-08deeaade3da")


class _Flavor(str, Enum):
    PDF = "pdf"


class _Rank(Enum):
    """A plain Enum: not a str subclass, so json.dumps cannot encode it."""

    HIGH = 1


def _llm_context(tool_name: str) -> MockingContext:
    return MockingContext(
        strategy=LLMMockingStrategy(
            prompt="simulate it",
            tools_to_simulate=[ToolSimulation(name=tool_name)],
        ),
        name="test-run",
        inputs={},
    )


class TestLLMMockerArgSerialization:
    """LLMMocker builds its prompt with json.dumps over the raw invocation."""

    def teardown_method(self):
        clear_execution_context()

    @pytest.mark.asyncio
    async def test_uuid_argument_does_not_break_prompt_generation(self):
        captured: dict[str, Any] = {}

        async def _fake_generate(llm, messages, **kwargs):
            captured["prompt"] = messages[0]["content"]
            return {"ok": True}

        @mockable()
        async def extraction_tool(**kwargs: Any) -> dict[str, Any]:
            raise NotImplementedError("must be simulated, never executed")

        set_execution_context(
            _llm_context("extraction_tool"), _mock_span_collector, "exec-uuid"
        )
        with (
            patch("uipath.eval.mocks._llm_mocker.UiPath", MagicMock()),
            patch("uipath.eval.mocks._llm_mocker.UiPathLlmChatService", MagicMock()),
            patch(
                "uipath.eval.mocks._llm_mocker.generate_structured_output",
                _fake_generate,
            ),
        ):
            result = await extraction_tool(
                id=_ATTACHMENT_ID,
                full_name="PO_234.pdf",
                mime_type="application/pdf",
            )

        assert result == {"ok": True}
        # The UUID must reach the prompt in its string form.
        assert str(_ATTACHMENT_ID) in captured["prompt"]

    @pytest.mark.asyncio
    async def test_other_non_json_native_arguments_are_serialized(self):
        captured: dict[str, Any] = {}

        async def _fake_generate(llm, messages, **kwargs):
            captured["prompt"] = messages[0]["content"]
            return {"ok": True}

        @mockable()
        async def typed_tool(**kwargs: Any) -> dict[str, Any]:
            raise NotImplementedError()

        set_execution_context(
            _llm_context("typed_tool"), _mock_span_collector, "exec-typed"
        )
        with (
            patch("uipath.eval.mocks._llm_mocker.UiPath", MagicMock()),
            patch("uipath.eval.mocks._llm_mocker.UiPathLlmChatService", MagicMock()),
            patch(
                "uipath.eval.mocks._llm_mocker.generate_structured_output",
                _fake_generate,
            ),
        ):
            await typed_tool(
                when=datetime(2026, 7, 27, 12, 39, 59, tzinfo=timezone.utc),
                flavor=_Flavor.PDF,
                rank=_Rank.HIGH,
                tags={"alpha", "beta"},
            )

        prompt = captured["prompt"]
        assert "2026-07-27T12:39:59" in prompt
        assert "pdf" in prompt
        # A plain (non-str) Enum must be reduced to its value.
        assert '"rank": 1' in prompt
        # Sets become lists; assert on members so the check stays order-independent.
        assert '"alpha"' in prompt
        assert '"beta"' in prompt


class TestSimulateComponentPayloadSerialization:
    """The simulate-component payload is encoded by httpx with a bare json.dumps."""

    def teardown_method(self):
        clear_execution_context()

    @pytest.mark.asyncio
    @pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
    async def test_uuid_in_payload_is_sent_as_string(
        self, httpx_mock: HTTPXMock, monkeypatch: MonkeyPatch
    ):
        monkeypatch.setenv("UIPATH_URL", "https://example.com/myorg/mytenant")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "token")
        httpx_mock.add_response(
            url="https://example.com/myorg/mytenant/agentsruntime_/api/execution/simulations/simulate-component",
            method="POST",
            json={"status": 1, "simulatedOutput": "result"},
        )

        service = _create_simulate_component_service()
        result = await service.simulate(
            {
                "componentId": "extraction_tool",
                "input": {
                    "args": [],
                    "kwargs": {
                        "id": _ATTACHMENT_ID,
                        "when": datetime(2026, 7, 27, 12, 39, 59, tzinfo=timezone.utc),
                        "rank": _Rank.HIGH,
                        "tags": {"alpha", "beta"},
                    },
                },
            }
        )

        assert result == {"status": 1, "simulatedOutput": "result"}
        sent_kwargs = json.loads(httpx_mock.get_requests()[-1].read())["input"][
            "kwargs"
        ]
        assert sent_kwargs["id"] == str(_ATTACHMENT_ID)
        assert sent_kwargs["when"].startswith("2026-07-27T12:39:59")
        assert sent_kwargs["rank"] == 1
        assert sorted(sent_kwargs["tags"]) == ["alpha", "beta"]

    @pytest.mark.asyncio
    async def test_mocker_end_to_end_with_uuid_argument(self):
        captured: list[dict[str, Any]] = []

        async def _capture(payload, **kwargs):
            captured.append(payload)
            return {"status": 1, "simulatedOutput": "ok"}

        svc_mock = MagicMock()
        svc_mock.simulate = _capture

        @mockable()
        async def extraction_tool(**kwargs: Any) -> str:
            raise NotImplementedError()

        context = MockingContext(
            strategy=None,
            name="test-run",
            inputs={},
            workload_id="wl-1",
            components=[
                ComponentSimulationConfig(
                    component_id="extraction_tool",
                    simulation_strategy=SimulationStrategy.LLM,
                )
            ],
        )
        set_execution_context(context, _mock_span_collector, "exec-e2e")
        with patch(
            "uipath.eval.mocks._simulate_component_mocker._create_simulate_component_service",
            return_value=svc_mock,
        ):
            result = await extraction_tool(id=_ATTACHMENT_ID)

        assert result == "ok"
        assert captured[0]["input"]["kwargs"]["id"] == _ATTACHMENT_ID


class TestSimulateComponentServiceUnchangedBehaviour:
    """Normalization must not alter payloads that already serialized cleanly."""

    @pytest.mark.asyncio
    @pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
    async def test_json_native_payload_is_unchanged(
        self, httpx_mock: HTTPXMock, monkeypatch: MonkeyPatch
    ):
        monkeypatch.setenv("UIPATH_URL", "https://example.com/myorg/mytenant")
        monkeypatch.setenv("UIPATH_ACCESS_TOKEN", "token")
        httpx_mock.add_response(
            url="https://example.com/myorg/mytenant/agentsruntime_/api/execution/simulations/simulate-component",
            method="POST",
            json={"status": 1, "simulatedOutput": "result"},
        )

        payload: dict[str, Any] = {
            "componentId": "my_tool",
            "componentType": "tool",
            "input": {"args": [1, "two", True, None], "kwargs": {"nested": {"a": 1.5}}},
            "behaviors": None,
            "simulationStrategy": 0,
        }
        service = _create_simulate_component_service()
        await service.simulate(payload)

        sent = json.loads(httpx_mock.get_requests()[-1].read())
        assert sent == payload
