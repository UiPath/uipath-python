"""Silent debug bridge for polling mode - minimal output, no interactive debugging."""

import asyncio
import json
import logging
import signal
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from uipath.runtime import UiPathRuntimeResult
from uipath.runtime.debug import UiPathDebugQuitError
from uipath.runtime.events import UiPathRuntimeStateEvent
from uipath.runtime.resumable import UiPathResumeTriggerType

logger = logging.getLogger(__name__)


class SilentDebugBridge:
    """A minimal debug bridge for polling mode - no interactive output."""

    def __init__(self):
        self._terminate_event: asyncio.Event | None = None
        self._waiting_for_api_input = False
        self._stdin_executor = ThreadPoolExecutor(max_workers=1)

    async def connect(self) -> None:
        self._terminate_event = asyncio.Event()
        signal.signal(signal.SIGINT, self._handle_sigint)

    async def disconnect(self) -> None:
        pass

    async def emit_execution_started(self, **kwargs) -> None:
        logger.debug("Execution started (polling mode)")

    async def emit_state_update(self, state_event: UiPathRuntimeStateEvent) -> None:
        if state_event.node_name == "<polling>":
            logger.info(
                f"Polling for trigger... (attempt {state_event.payload.get('attempt', '?')})"
            )

    async def emit_breakpoint_hit(self, breakpoint_result: Any) -> None:
        pass  # No breakpoints in polling mode

    async def emit_execution_completed(
        self, runtime_result: UiPathRuntimeResult
    ) -> None:
        logger.debug(f"Execution completed: {runtime_result.status}")

    async def emit_execution_suspended(
        self, runtime_result: UiPathRuntimeResult
    ) -> None:
        if (
            runtime_result.trigger
            and runtime_result.trigger.trigger_type == UiPathResumeTriggerType.API
        ):
            self._waiting_for_api_input = True
            print("API trigger suspended. Please provide JSON input:")

    async def emit_execution_resumed(self, resume_data: Any) -> None:
        logger.debug("Execution resumed")

    async def emit_execution_error(self, error: str) -> None:
        logger.error(f"Execution error: {error}")

    async def wait_for_resume(self) -> dict[str, Any] | None:
        """Wait for resume - prompt for input on API triggers."""
        if self._waiting_for_api_input:
            self._waiting_for_api_input = False
            loop = asyncio.get_running_loop()
            try:
                user_input = await loop.run_in_executor(
                    self._stdin_executor, self._read_input_blocking
                )
                stripped = user_input.strip()
                if not stripped:
                    return {}
                try:
                    return json.loads(stripped)
                except json.JSONDecodeError:
                    return stripped
            except (KeyboardInterrupt, EOFError):
                raise UiPathDebugQuitError("User interrupted")
        return None  # Non-API triggers don't need user input

    async def wait_for_terminate(self) -> None:
        assert self._terminate_event is not None
        await self._terminate_event.wait()

    def get_breakpoints(self) -> list[str] | Literal["*"]:
        return []  # No breakpoints

    def _read_input_blocking(self) -> str:
        assert self._terminate_event is not None
        try:
            return input("> ")
        except KeyboardInterrupt as e:
            self._terminate_event.set()
            raise UiPathDebugQuitError("User pressed Ctrl+C") from e
        except EOFError as e:
            self._terminate_event.set()
            raise UiPathDebugQuitError("STDIN closed by user") from e

    def _handle_sigint(self, signum: int, frame: Any) -> None:
        if self._terminate_event:
            asyncio.get_running_loop().call_soon_threadsafe(self._terminate_event.set)
