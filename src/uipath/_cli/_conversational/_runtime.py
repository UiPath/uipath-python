import logging
from typing import TypeVar, Generic, Optional

from uipath._events._events import (
    UiPathAgentMessageEvent,
)

from .._runtime._contracts import (
    UiPathBaseRuntime,
    UiPathRuntimeContext,
    UiPathRuntimeFactory,
    UiPathRuntimeResult,
    UiPathRuntimeStreamNotSupportedError,
)

from ._bridge import  UiPathConversationBridge

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=UiPathBaseRuntime)
C = TypeVar("C", bound=UiPathRuntimeContext)

class UiPathConversationRuntime(UiPathBaseRuntime, Generic[T, C]):
    """Runtime for conversational coded agents"""

    def __init__(
        self,
        context: UiPathRuntimeContext,
        factory: UiPathRuntimeFactory[T, C],
        conversation_bridge: UiPathConversationBridge
    ):
        super().__init__(context)
        self.context: UiPathRuntimeContext = context
        self.factory: UiPathRuntimeFactory[T, C] = factory
        self.conversation_bridge: UiPathConversationBridge = conversation_bridge
        self._inner_runtime: Optional[T] = None

    @classmethod
    def from_conversation_context(
        cls,
        context: UiPathRuntimeContext,
        factory: UiPathRuntimeFactory[T, C],
        conversation_bridge: UiPathConversationBridge,
    ) -> "UiPathConversationRuntime[T, C]":
        return cls(context, factory, conversation_bridge)

    async def execute(self) -> Optional[UiPathRuntimeResult]:
        """Execute the conversational agent and stream messages."""
        try:
            await self.conversation_bridge.connect()

            self._inner_runtime = self.factory.new_runtime()

            if not self._inner_runtime:
                raise RuntimeError("Failed to create inner runtime")

            # Try to stream events from inner runtime
            try:
                self.context.result = await self._stream_events()
            except UiPathRuntimeStreamNotSupportedError:
                # Fallback to regular execute if streaming not supported
                logger.debug(
                    f"Runtime {self._inner_runtime.__class__.__name__} does not support "
                    "streaming, falling back to execute()"
                )
                self.context.result = await self._inner_runtime.execute()

            return self.context.result

        except Exception as e:
            logger.error(f"Conversation execution error: {str(e)}")
            raise

    async def _stream_events(self) -> Optional[UiPathRuntimeResult]:
        """Stream message events from inner runtime."""
        if not self._inner_runtime:
            return None

        final_result: Optional[UiPathRuntimeResult] = None

        # Stream events from inner runtime
        async for event in self._inner_runtime.stream():
            # Handle final result
            if isinstance(event, UiPathRuntimeResult):
                final_result = event

            # Handle message events - forward to conversation bridge
            elif isinstance(event, UiPathAgentMessageEvent):
                logger.warning("SendingEvent")
                await self.conversation_bridge.emit_message(event)

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
                conversation_id = getattr(self.context, "conversation_id", None) or self.context.execution_id
                exchange_id = getattr(self.context, "exchange_id", None) or self.context.execution_id
                await self.conversation_bridge.disconnect(conversation_id, exchange_id)
            except Exception as e:
                logger.warning(f"Error disconnecting conversation bridge: {e}")






