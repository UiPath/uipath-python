import pytest
from pytest_httpx import HTTPXMock

from uipath._config import Config
from uipath._execution_context import ExecutionContext
from uipath._services.conversations_service import ConversationsService
from uipath.agent.conversation import UiPathConversationMessage


@pytest.fixture
def service(
    config: Config, execution_context: ExecutionContext
) -> ConversationsService:
    return ConversationsService(config=config, execution_context=execution_context)


class TestConversationsService:
    class TestRetrieveMessage:
        @pytest.mark.anyio
        async def test_retrieve_message(
            self,
            httpx_mock: HTTPXMock,
            service: ConversationsService,
            base_url: str,
            org: str,
            tenant: str,
            version: str,
        ) -> None:
            """Test retrieving a specific message from an exchange."""
            conversation_id = "123"
            exchange_id = "202cf2d1-926e-422d-8cf2-4f5735fa91fa"
            message_id = "08de239e-90da-4d17-b986-b7785268d8d7"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/autopilotforeveryone_/api/v1/conversation/{conversation_id}/exchange/{exchange_id}/message/{message_id}",
                status_code=200,
                json={
                    "messageId": message_id,
                    "role": "assistant",
                    "contentParts": [],
                    "createdAt": "2024-01-01T00:00:00Z",
                    "updatedAt": "2024-01-01T00:00:00Z",
                },
            )

            result = await service.retrieve_message_async(
                conversation_id=conversation_id,
                exchange_id=exchange_id,
                message_id=message_id,
            )

            assert isinstance(result, UiPathConversationMessage)
            assert result.message_id == message_id
            assert result.role == "assistant"

            sent_request = httpx_mock.get_request()
            if sent_request is None:
                raise Exception("No request was sent")

            assert sent_request.method == "GET"
            assert (
                sent_request.url
                == f"{base_url}{org}{tenant}/autopilotforeveryone_/api/v1/conversation/{conversation_id}/exchange/{exchange_id}/message/{message_id}"
            )

        @pytest.mark.anyio
        async def test_retrieve_message_with_content_parts(
            self,
            httpx_mock: HTTPXMock,
            service: ConversationsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            """Test retrieving a message with content parts."""
            conversation_id = "123"
            exchange_id = "202cf2d1-926e-422d-8cf2-4f5735fa91fa"
            message_id = "08de239e-90da-4d17-b986-b7785268d8d7"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/autopilotforeveryone_/api/v1/conversation/{conversation_id}/exchange/{exchange_id}/message/{message_id}",
                status_code=200,
                json={
                    "messageId": message_id,
                    "role": "user",
                    "contentParts": [
                        {
                            "contentPartId": "cp-1",
                            "mimeType": "text/plain",
                            "data": {"inline": "Hello, world!"},
                        }
                    ],
                    "createdAt": "2024-01-01T00:00:00Z",
                    "updatedAt": "2024-01-01T00:00:00Z",
                },
            )

            result = await service.retrieve_message_async(
                conversation_id=conversation_id,
                exchange_id=exchange_id,
                message_id=message_id,
            )

            assert isinstance(result, UiPathConversationMessage)
            assert result.message_id == message_id
            assert result.role == "user"
            assert result.content_parts is not None
            assert len(result.content_parts) == 1
            assert result.content_parts[0].content_part_id == "cp-1"
            assert result.content_parts[0].mime_type == "text/plain"

        @pytest.mark.anyio
        async def test_retrieve_message_with_tool_calls(
            self,
            httpx_mock: HTTPXMock,
            service: ConversationsService,
            base_url: str,
            org: str,
            tenant: str,
        ) -> None:
            """Test retrieving a message with tool calls."""
            conversation_id = "123"
            exchange_id = "202cf2d1-926e-422d-8cf2-4f5735fa91fa"
            message_id = "08de239e-90da-4d17-b986-b7785268d8d7"

            httpx_mock.add_response(
                url=f"{base_url}{org}{tenant}/autopilotforeveryone_/api/v1/conversation/{conversation_id}/exchange/{exchange_id}/message/{message_id}",
                status_code=200,
                json={
                    "messageId": message_id,
                    "role": "assistant",
                    "contentParts": [],
                    "toolCalls": [
                        {
                            "toolCallId": "tc-1",
                            "name": "get_weather",
                            "arguments": {"inline": '{"city": "San Francisco"}'},
                        }
                    ],
                    "createdAt": "2024-01-01T00:00:00Z",
                    "updatedAt": "2024-01-01T00:00:00Z",
                },
            )

            result = await service.retrieve_message_async(
                conversation_id=conversation_id,
                exchange_id=exchange_id,
                message_id=message_id,
            )

            assert isinstance(result, UiPathConversationMessage)
            assert result.message_id == message_id
            assert result.role == "assistant"
            assert result.tool_calls is not None
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0].tool_call_id == "tc-1"
            assert result.tool_calls[0].name == "get_weather"
