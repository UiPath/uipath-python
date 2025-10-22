import os
from typing import List, Optional

from uipath._cli._runtime._contracts import (
    UiPathRuntimeContext,
    UiPathRuntimeFactory,
)
from uipath._cli._runtime._runtime import UiPathScriptRuntime, get_user_scripts


class UiPathScriptRuntimeFactory(
    UiPathRuntimeFactory[UiPathScriptRuntime, UiPathRuntimeContext]
):
    """Factory for Python script runtimes."""

    def __init__(self):
        super().__init__(
            UiPathScriptRuntime,
            UiPathRuntimeContext,
            context_generator=lambda **kwargs: UiPathRuntimeContext.with_defaults(
                **kwargs
            ),
        )

    def discover_all_runtimes(self) -> List[UiPathScriptRuntime]:
        """Get a list of all available Python script runtimes."""
        scripts = get_user_scripts(os.getcwd())

        runtimes = []
        for script_path in scripts:
            runtime = self._create_runtime(script_path)
            if runtime:
                runtimes.append(runtime)

        return runtimes

    def get_runtime(self, entrypoint: str) -> Optional[UiPathScriptRuntime]:
        """Get runtime for a specific Python script."""
        if not os.path.isabs(entrypoint):
            script_path = os.path.abspath(entrypoint)
        else:
            script_path = entrypoint

        if not os.path.isfile(script_path) or not script_path.endswith(".py"):
            return None

        return self._create_runtime(script_path)

    def _create_runtime(self, script_path: str) -> Optional[UiPathScriptRuntime]:
        """Create runtime instance for a script path."""
        context = self.new_context(entrypoint=script_path)
        runtime = self.from_context(context)
        return runtime
