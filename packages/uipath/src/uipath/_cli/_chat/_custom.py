"""Loading a chat bridge the project supplies itself.

The Conversational Agent Service is one place an exchange can be spoken to, not
the only one. A project that names a ``chatBridge`` in uipath.json is telling
the runtime where its messages go instead: Slack, Teams, a webhook, a test
double. The runtime already speaks to all of them through
``UiPathChatProtocol``, so nothing framework-specific is involved and every
agent framework gets the same reach for free.
"""

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Any, Callable

from uipath.runtime.chat import UiPathChatProtocol
from uipath.runtime.context import UiPathRuntimeContext

logger = logging.getLogger(__name__)

ChatBridgeFactory = Callable[[UiPathRuntimeContext], UiPathChatProtocol | None]


class UiPathChatBridgeError(Exception):
    """A configured chat bridge could not be loaded."""


def _load_factory(spec: str) -> ChatBridgeFactory:
    if ":" not in spec:
        raise UiPathChatBridgeError(
            f"chatBridge must be 'file_path:factory_name', got {spec!r}."
        )
    file_part, _, factory_name = spec.partition(":")

    path = Path(file_part).resolve()
    if not path.is_file():
        raise UiPathChatBridgeError(f"chatBridge file not found: {path}")

    module_name = f"_uipath_chat_bridge_{path.stem}"
    module_spec = importlib.util.spec_from_file_location(module_name, path)
    if module_spec is None or module_spec.loader is None:
        raise UiPathChatBridgeError(f"chatBridge file is not importable: {path}")

    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_name] = module
    module_spec.loader.exec_module(module)

    factory: Any = getattr(module, factory_name, None)
    if factory is None:
        raise UiPathChatBridgeError(f"{path.name} has no attribute {factory_name!r}.")
    if not callable(factory):
        raise UiPathChatBridgeError(f"{spec} is not callable.")
    return factory


def resolve_chat_bridge(
    spec: str | None, context: UiPathRuntimeContext
) -> UiPathChatProtocol | None:
    """Build the project's own chat bridge, if it declared one and it wants this run.

    A factory returning ``None`` declines, which is how one agent serves both a
    custom surface and the Conversational Agent Service without branching.
    """
    if not spec:
        return None
    bridge = _load_factory(spec)(context)
    if bridge is None:
        logger.debug("chatBridge %s declined this run.", spec)
    return bridge
