"""UiPath Functions Runtime - factory and runtime for function-based execution."""

from uipath.platform.constants import UIPATH_CONFIG_FILE
from uipath.runtime import UiPathRuntimeFactoryRegistry

from .debug import UiPathDebugFunctionsRuntime
from .factory import UiPathFunctionsRuntimeFactory
from .runtime import UiPathFunctionsRuntime


def register_default_runtime_factory():
    """Register the default functions factory."""
    UiPathRuntimeFactoryRegistry.register(
        "uipath",
        factory_callable=lambda context: UiPathFunctionsRuntimeFactory(
            config_path=UIPATH_CONFIG_FILE,
        ),
        config_file=UIPATH_CONFIG_FILE,
    )
    UiPathRuntimeFactoryRegistry.set_default("uipath")


__all__ = [
    "UiPathDebugFunctionsRuntime",
    "UiPathFunctionsRuntimeFactory",
    "UiPathFunctionsRuntime",
    "register_default_runtime_factory",
]
