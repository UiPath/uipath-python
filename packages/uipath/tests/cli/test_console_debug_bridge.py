"""Tests for how `ConsoleDebugBridge` renders payloads.

A run's output is the result the user asked for, so it must print whole.
Intermediate state is a progress stream and may still be shortened.
"""

from typing import Any

from pydantic import BaseModel
from rich.console import Console

from uipath._cli._debug._bridge import ConsoleDebugBridge
from uipath.core.triggers import UiPathResumeTrigger, UiPathResumeTriggerType
from uipath.runtime import UiPathRuntimeResult, UiPathRuntimeStatus
from uipath.runtime.events import UiPathRuntimeStateEvent, UiPathRuntimeStatePhase

# 256 characters, the length from the original report. The tail is distinct
# so a cut at 250 cannot pass by accident.
LONG = "x" * 240 + "0123456789ABCDEF"


def _bridge() -> ConsoleDebugBridge:
    bridge = ConsoleDebugBridge()
    # Wide enough that rich never wraps a value across lines.
    bridge.console = Console(record=True, width=2000, color_system=None)
    return bridge


async def _render_output(output: Any) -> str:
    bridge = _bridge()
    await bridge.emit_execution_completed(
        UiPathRuntimeResult(output=output, status=UiPathRuntimeStatus.SUCCESSFUL)
    )
    return bridge.console.export_text()


async def test_completed_output_prints_long_value_whole() -> None:
    text = await _render_output({"dials": LONG})

    assert LONG in text
    assert "..." not in text


async def test_completed_output_prints_long_values_nested_and_in_lists() -> None:
    text = await _render_output(
        {"outer": {"inner": LONG}, "items": [LONG, {"deep": LONG}]}
    )

    assert text.count(LONG) == 3


async def test_completed_output_prints_long_string_output_whole() -> None:
    text = await _render_output(LONG)

    assert LONG in text


async def test_completed_output_prints_pydantic_model_whole() -> None:
    class Output(BaseModel):
        dials: str

    text = await _render_output(Output(dials=LONG))

    assert LONG in text


async def test_completed_output_keeps_nesting_deeper_than_ten() -> None:
    payload: dict[str, Any] = {"leaf": "bottom-value"}
    for i in range(15):
        payload = {f"level{i}": payload}

    text = await _render_output(payload)

    assert "bottom-value" in text


async def test_completed_output_prints_markup_like_text_literally() -> None:
    text = await _render_output(
        {"[b]key[/b]": "see [bold]docs[/bold]", "note": "close [/x] tag"}
    )

    assert "see [bold]docs[/bold]" in text
    assert "close [/x] tag" in text
    assert "[b]key[/b]" in text
    # A render error would switch to the JSON fallback, which prints the label
    # as "output:" instead of a tree root.
    assert "output:" not in text


async def test_suspended_api_output_prints_long_value_whole() -> None:
    bridge = _bridge()
    await bridge.emit_execution_suspended(
        UiPathRuntimeResult(
            output={"question": LONG},
            status=UiPathRuntimeStatus.SUSPENDED,
            trigger=UiPathResumeTrigger(trigger_type=UiPathResumeTriggerType.API),
        )
    )

    assert LONG in bridge.console.export_text()


async def test_state_update_still_shortens_long_values() -> None:
    bridge = _bridge()
    await bridge.emit_state_update(
        UiPathRuntimeStateEvent(
            node_name="node",
            phase=UiPathRuntimeStatePhase.UPDATED,
            payload={"state": LONG},
        )
    )
    text = bridge.console.export_text()

    assert LONG not in text
    assert LONG[:250] + "..." in text
