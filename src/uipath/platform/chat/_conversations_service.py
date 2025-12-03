from uipath.core.chat import UiPathConversationMessage

from ..._utils import Endpoint, RequestSpec
from ...tracing import traced
from ..common import BaseService, UiPathApiConfig, UiPathExecutionContext


class ConversationsService(BaseService):
    def __init__(
        self, config: UiPathApiConfig, execution_context: UiPathExecutionContext
    ) -> None:
        super().__init__(config=config, execution_context=execution_context)

    @traced(name="retrieve_message", run_type="uipath")
    def retrieve_message(
        self, conversation_id: str, exchange_id: str, message_id: str
    ) -> UiPathConversationMessage:
        retrieve_message_spec = self._retrieve_message_spec(
            conversation_id, exchange_id, message_id
        )

        response = self.request(
            retrieve_message_spec.method, retrieve_message_spec.endpoint
        )

        return UiPathConversationMessage.model_validate(response.json())

    @traced(name="retrieve_message", run_type="uipath")
    async def retrieve_message_async(
        self, conversation_id: str, exchange_id: str, message_id: str
    ) -> UiPathConversationMessage:
        retrieve_message_spec = self._retrieve_message_spec(
            conversation_id, exchange_id, message_id
        )

        response = await self.request_async(
            retrieve_message_spec.method, retrieve_message_spec.endpoint
        )

        return UiPathConversationMessage.model_validate(response.json())

    def _retrieve_message_spec(
        self, conversation_id: str, exchange_id: str, message_id: str
    ) -> RequestSpec:
        return RequestSpec(
            method="GET",
            endpoint=Endpoint(
                f"/autopilotforeveryone_/api/v1/conversation/{conversation_id}/exchange/{exchange_id}/message/{message_id}"
            ),
        )
