from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import pytest

from uipath.core.triggers import (
    UiPathResumeTrigger,
    UiPathResumeTriggerName,
    UiPathResumeTriggerType,
)
from uipath.platform.resume_triggers import UiPathResumeTriggerHandler, WaitUntil
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathResumableRuntime,
    UiPathResumableStorageProtocol,
    UiPathResumeTriggerProtocol,
    UiPathRuntimeEvent,
    UiPathRuntimeProtocol,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathStreamOptions,
)
from uipath.runtime.schema import UiPathRuntimeSchema


class SuspendedRuntime:
    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        del input, options
        return UiPathRuntimeResult(
            status=UiPathRuntimeStatus.SUSPENDED,
            output={
                "interrupt-1": WaitUntil(
                    resume_time=datetime(2026, 7, 6, 12, tzinfo=timezone.utc)
                )
            },
        )

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        yield await self.execute(input, options)

    async def get_schema(self) -> UiPathRuntimeSchema:
        return UiPathRuntimeSchema(
            filePath="agent.py",
            uniqueId="agent",
            type="test",
            input={},
            output={},
        )

    async def dispose(self) -> None:
        pass


class MemoryResumableStorage:
    def __init__(self) -> None:
        self.triggers: list[UiPathResumeTrigger] | None = None
        self.saved_runtime_id: str | None = None

    async def set_value(
        self, runtime_id: str, namespace: str, key: str, value: Any
    ) -> None:
        del runtime_id, namespace, key, value

    async def get_value(self, runtime_id: str, namespace: str, key: str) -> Any:
        del runtime_id, namespace, key
        return None

    async def save_triggers(
        self, runtime_id: str, triggers: list[UiPathResumeTrigger]
    ) -> None:
        self.saved_runtime_id = runtime_id
        self.triggers = triggers

    async def get_triggers(self, runtime_id: str) -> list[UiPathResumeTrigger] | None:
        del runtime_id
        return self.triggers

    async def delete_triggers(
        self, runtime_id: str, triggers: list[UiPathResumeTrigger]
    ) -> None:
        del runtime_id
        if self.triggers is None:
            return
        self.triggers = [
            trigger for trigger in self.triggers if trigger not in triggers
        ]

    async def delete_trigger(
        self, runtime_id: str, trigger: UiPathResumeTrigger
    ) -> None:
        await self.delete_triggers(runtime_id, [trigger])


@pytest.mark.anyio
async def test_platform_handler_satisfies_runtime_trigger_protocol() -> None:
    handler: UiPathResumeTriggerProtocol = UiPathResumeTriggerHandler()

    triggers = await handler.create_triggers(
        WaitUntil(resume_time=datetime(2026, 7, 6, 12, tzinfo=timezone.utc))
    )

    assert len(triggers) == 1
    assert triggers[0].trigger_type == UiPathResumeTriggerType.TIMER
    assert triggers[0].trigger_name == UiPathResumeTriggerName.TIMER


@pytest.mark.anyio
async def test_resumable_runtime_uses_platform_trigger_protocol() -> None:
    delegate: UiPathRuntimeProtocol = SuspendedRuntime()
    memory_storage = MemoryResumableStorage()
    storage: UiPathResumableStorageProtocol = memory_storage
    handler: UiPathResumeTriggerProtocol = UiPathResumeTriggerHandler()

    runtime = UiPathResumableRuntime(
        delegate=delegate,
        storage=storage,
        trigger_manager=handler,
        runtime_id="runtime-1",
    )

    result = await runtime.execute()

    assert result.status == UiPathRuntimeStatus.SUSPENDED
    assert memory_storage.saved_runtime_id == "runtime-1"
    assert result.triggers is not None
    assert len(result.triggers) == 1
    assert result.triggers[0].interrupt_id == "interrupt-1"
    assert result.triggers[0].trigger_type == UiPathResumeTriggerType.TIMER
    assert result.triggers[0].trigger_name == UiPathResumeTriggerName.TIMER
