import asyncio
import logging
from typing import Generic, Optional, TypeVar

from uipath._events._events import (
    UiPathAgentStateEvent,
)

from .._runtime._contracts import (
    UiPathBaseRuntime,
    UiPathBreakpointResult,
    UiPathRuntimeContext,
    UiPathRuntimeFactory,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathRuntimeStreamNotSupportedError,
)
from ._bridge import DebuggerQuitException, UiPathDebugBridge

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=UiPathBaseRuntime)
C = TypeVar("C", bound=UiPathRuntimeContext)


class UiPathDebugRuntime(UiPathBaseRuntime, Generic[T, C]):
    """Specialized runtime for debug runs that streams events to a debug bridge."""

    def __init__(
        self,
        context: UiPathRuntimeContext,
        factory: UiPathRuntimeFactory[T, C],
        debug_bridge: UiPathDebugBridge,
    ):
        super().__init__(context)
        self.context: UiPathRuntimeContext = context
        self.factory: UiPathRuntimeFactory[T, C] = factory
        self.debug_bridge: UiPathDebugBridge = debug_bridge
        self.execution_id: str = context.job_id or "default"
        self._inner_runtime: Optional[T] = None

    @classmethod
    def from_debug_context(
        cls,
        context: UiPathRuntimeContext,
        factory: UiPathRuntimeFactory[T, C],
        debug_bridge: UiPathDebugBridge,
    ) -> "UiPathDebugRuntime[T, C]":
        return cls(context, factory, debug_bridge)

    async def execute(self) -> Optional[UiPathRuntimeResult]:
        """Execute the workflow with debug support."""
        try:
            await self.debug_bridge.connect()

            self._inner_runtime = self.factory.new_runtime()

            if not self._inner_runtime:
                raise RuntimeError("Failed to create inner runtime")

            await self.debug_bridge.emit_execution_started(
                execution_id=self.execution_id
            )

            # Try to stream events from inner runtime
            try:
                self.context.result = await self._stream_and_debug()
            except UiPathRuntimeStreamNotSupportedError:
                # Fallback to regular execute if streaming not supported
                logger.debug(
                    f"Runtime {self._inner_runtime.__class__.__name__} does not support "
                    "streaming, falling back to execute()"
                )
                self.context.result = await self._inner_runtime.execute()

            if self.context.result:
                await self.debug_bridge.emit_execution_completed(self.context.result)

            return self.context.result

        except Exception as e:
            # Emit execution error
            self.context.result = UiPathRuntimeResult(
                status=UiPathRuntimeStatus.FAULTED,
            )
            await self.debug_bridge.emit_execution_error(
                execution_id=self.execution_id,
                error=str(e),
            )
            raise

    async def _stream_and_debug(self) -> Optional[UiPathRuntimeResult]:
        """Stream events from inner runtime and handle debug interactions."""
        if not self._inner_runtime:
            return None

        final_result: Optional[UiPathRuntimeResult] = None
        execution_completed = False

        # Starting in paused state - wait for breakpoints and resume
        try:
            await asyncio.wait_for(self.debug_bridge.wait_for_resume(), timeout=60.0)
        except asyncio.TimeoutError:
            logger.warning(
                "Initial resume wait timed out after 60s, assuming debug bridge disconnected"
            )
            return UiPathRuntimeResult(
                status=UiPathRuntimeStatus.SUCCESSFUL,
            )

        # Keep streaming until execution completes (not just paused at breakpoint)
        while not execution_completed:
            # Update breakpoints from debug bridge
            self._inner_runtime.context.breakpoints = (
                self.debug_bridge.get_breakpoints()
            )
            # Stream events from inner runtime
            async for event in self._inner_runtime.stream():
                # Handle final result
                if isinstance(event, UiPathRuntimeResult):
                    final_result = event

                    # Check if it's a breakpoint result
                    if isinstance(event, UiPathBreakpointResult):
                        try:
                            # Hit a breakpoint - wait for resume and continue
                            await self.debug_bridge.emit_breakpoint_hit(event)
                            await self.debug_bridge.wait_for_resume()

                            self._inner_runtime.context.resume = True

                        except DebuggerQuitException:
                            final_result = UiPathRuntimeResult(
                                status=UiPathRuntimeStatus.SUCCESSFUL,
                            )
                            execution_completed = True
                    else:
                        # Normal completion or suspension with dynamic interrupt
                        execution_completed = True
                        # Handle dynamic interrupts if present
                        # Maybe poll for resume trigger completion here in future

                # Handle state update events - send to debug bridge
                elif isinstance(event, UiPathAgentStateEvent):
                    await self.debug_bridge.emit_state_update(event)

        return final_result

    async def validate(self) -> None:
        """Validate runtime configuration."""
        if self._inner_runtime:
            await self._inner_runtime.validate()

    async def cleanup(self) -> None:
        """Cleanup runtime resources."""
        try:
            if self._inner_runtime:
                await self._inner_runtime.cleanup()
        finally:
            try:
                await self.debug_bridge.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting debug bridge: {e}")
