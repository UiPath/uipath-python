import asyncio
from typing import Any, Dict, Generic, List, Optional, TypeVar

from .._runtime._contracts import (
    UiPathBaseRuntime,
    UiPathRuntimeContext,
    UiPathRuntimeFactory,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)
from ._bridge import IDebugBridge

T = TypeVar("T", bound=UiPathBaseRuntime)
C = TypeVar("C", bound=UiPathRuntimeContext)


class UiPathDebugRuntime(UiPathBaseRuntime, Generic[T, C]):
    """Specialized runtime for debug runs, with access to the factory."""

    def __init__(
        self,
        context: UiPathRuntimeContext,
        factory: UiPathRuntimeFactory[T, C],
        debug_bridge: IDebugBridge,
    ):
        super().__init__(context)
        self.context: UiPathRuntimeContext = context
        self.factory: UiPathRuntimeFactory[T, C] = factory
        self.debug_bridge: IDebugBridge = debug_bridge

        # Breakpoints should probably be part of the UiPathBaseRuntimeContext
        self.breakpoints = {
            "fetch_data": "before",
            "process_data": "after",
            "finalize": "before",
        }

    @classmethod
    def from_debug_context(
        cls,
        context: UiPathRuntimeContext,
        factory: UiPathRuntimeFactory[T, C],
        debug_bridge: IDebugBridge,
    ) -> "UiPathDebugRuntime[T, C]":
        return cls(context, factory, debug_bridge)

    async def execute(self) -> Optional[UiPathRuntimeResult]:
        """Debug the project workflow locally or via remote bridge."""
        await self.debug_bridge.connect()

        # Emit execution started
        await self.debug_bridge.emit_execution_started(
            execution_id=self.context.execution_id or "test-exec"
        )

        # Simulate workflow with multiple steps
        steps: List[Dict[str, Any]] = [
            {"name": "initialize", "data": {"status": "initializing"}},
            {"name": "fetch_data", "data": {"records": 42, "source": "database"}},
            {"name": "process_data", "data": {"processed": 42, "failed": 0}},
            {"name": "validate_results", "data": {"valid": True, "errors": []}},
            {"name": "finalize", "data": {"status": "complete"}},
        ]

        workflow_state: Dict[str, Any] = {"current_step": 0, "results": []}

        for i, step in enumerate(steps):
            location = step["name"]

            print(f"\n Executing step: {location}")

            if (
                location in self.breakpoints
                and self.breakpoints.get(location) == "before"
            ):
                print(f" Checking breakpoint BEFORE {location}")

                state_snapshot = {
                    "workflow_state": workflow_state,
                    "current_step": location,
                    "step_data": step["data"],
                }

                await self.debug_bridge.emit_breakpoint_hit(
                    execution_id=self.context.execution_id or "test-exec",
                    location=f"{location} (before)",
                    state=state_snapshot,
                    resume_trigger=None,
                )

                print(" Waiting for resume...")
                resume_data = await self.debug_bridge.wait_for_resume()
                print(" Resumed!")

                if resume_data is not None:
                    if isinstance(step["data"], dict):
                        step["data"].update({"resume_data": resume_data})

            # Simulate step execution
            await asyncio.sleep(0.5)  # Simulate work
            workflow_state["current_step"] = i + 1
            if isinstance(workflow_state["results"], list):
                workflow_state["results"].append(
                    {
                        "step": location,
                        "data": step["data"],
                    }
                )

            print(f" Completed step: {location}")

            # Check if we should break AFTER this step
            if (
                location in self.breakpoints
                and self.breakpoints.get(location) == "after"
            ):
                print(f" Checking breakpoint AFTER {location}")

                state_snapshot = {
                    "workflow_state": workflow_state,
                    "completed_step": location,
                    "step_result": step["data"],
                }

                # Notify debugger of breakpoint
                await self.debug_bridge.emit_breakpoint_hit(
                    execution_id=self.context.execution_id or "test-exec",
                    location=f"{location} (after)",
                    state=state_snapshot,
                    resume_trigger=None,
                )

                # Wait for resume command
                print(f"Suspended after {location}, waiting for resume...")
                await self.debug_bridge.wait_for_resume()
                print(f"Resumed after {location}!")

        # Emit execution completed
        await self.debug_bridge.emit_execution_completed(
            execution_id=self.context.execution_id or "test-exec",
            status=UiPathRuntimeStatus.SUCCESSFUL.value,
        )

        # Create result
        self.context.result = UiPathRuntimeResult(
            output=workflow_state,
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

        return self.context.result

    async def cleanup(self) -> None:
        """Cleanup runtime resources."""
        try:
            await self.debug_bridge.disconnect()
        except Exception:
            pass

    async def validate(self) -> None:
        """Validate runtime configuration."""
        pass
