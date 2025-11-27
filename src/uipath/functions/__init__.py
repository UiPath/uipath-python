"""UiPath Functions Runtime - factory and runtime for function-based execution."""

from uipath.runtime import UiPathRuntimeFactoryRegistry

from .factory import UiPathFunctionsRuntimeFactory
from .runtime import UiPathFunctionsRuntime


def register_default_runtime_factory():
    """Register the default functions factory."""
    UiPathRuntimeFactoryRegistry.register(
        "uipath",
        factory_callable=lambda context: UiPathFunctionsRuntimeFactory(
            config_path="uipath.json",
        ),
        config_file="uipath.json",
    )
    UiPathRuntimeFactoryRegistry.set_default("uipath")


__all__ = [
    "UiPathFunctionsRuntimeFactory",
    "UiPathFunctionsRuntime",
    "register_default_runtime_factory",
]
