import json
from typing import Any, Dict, List, Literal, Optional, Union

from langchain_core.callbacks import (
    AsyncCallbackManagerForLLMRun,
    CallbackManagerForLLMRun,
)
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.messages.ai import UsageMetadata
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable
from langchain_openai.chat_models import AzureChatOpenAI
from pydantic import BaseModel

from uipath_langchain._utils._request_mixin import UiPathRequestMixin
from uipath_langchain._utils._settings import UiPathEndpoints


class UiPathAzureChatOpenAI(UiPathRequestMixin, AzureChatOpenAI):
    """Custom LLM connector for LangChain integration with UiPath."""

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if "tools" in kwargs and not kwargs["tools"]:
            del kwargs["tools"]
        payload = self._get_request_payload(messages, stop=stop, **kwargs)
        response = self._call(self.url, payload, self.auth_headers)
        return self._create_chat_result(response)

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        if "tools" in kwargs and not kwargs["tools"]:
            del kwargs["tools"]
        payload = self._get_request_payload(messages, stop=stop, **kwargs)
        response = await self._acall(self.url, payload, self.auth_headers)
        return self._create_chat_result(response)

    def with_structured_output(
        self,
        schema: Optional[Any] = None,
        *,
        method: Literal["function_calling", "json_mode", "json_schema"] = "json_schema",
        include_raw: bool = False,
        strict: Optional[bool] = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, Any]:
        """Model wrapper that returns outputs formatted to match the given schema."""
        schema = (
            schema.model_json_schema()
            if isinstance(schema, type) and issubclass(schema, BaseModel)
            else schema
        )
        return super().with_structured_output(
            schema=schema,
            method=method,
            include_raw=include_raw,
            strict=strict,
            **kwargs,
        )

    @property
    def endpoint(self) -> str:
        return UiPathEndpoints.PASSTHROUGH_COMPLETION_ENDPOINT.value.format(
            model=self.model_name, api_version=self.openai_api_version
        )


class UiPathChat(UiPathRequestMixin, AzureChatOpenAI):
    """Custom LLM connector for LangChain integration with UiPath Normalized."""

    def _create_chat_result(
        self,
        response: Union[Dict[str, Any], BaseModel],
        generation_info: Optional[Dict[Any, Any]] = None,
    ) -> ChatResult:
        if not isinstance(response, dict):
            response = response.model_dump()
        message = response["choices"][0]["message"]
        usage = response["usage"]

        ai_message = AIMessage(
            content=message.get("content", ""),
            usage_metadata=UsageMetadata(
                input_tokens=usage.get("prompt_tokens", 0),
                output_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
            additional_kwargs={},
            response_metadata={
                "token_usage": response["usage"],
                "model_name": self.model_name,
                "finish_reason": response["choices"][0].get("finish_reason", None),
                "system_fingerprint": response["id"],
                "created": response["created"],
            },
        )

        if "tool_calls" in message:
            ai_message.tool_calls = [
                {
                    "id": tool["id"],
                    "name": tool["name"],
                    "args": tool["arguments"],
                }
                for tool in message["tool_calls"]
            ]
        generation = ChatGeneration(message=ai_message)
        return ChatResult(generations=[generation])

    def _get_request_payload(
        self,
        input_: LanguageModelInput,
        *,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[Any, Any]:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        # hacks to make the request work with uipath normalized
        for message in payload["messages"]:
            if message["content"] is None:
                message["content"] = ""
            if "tool_calls" in message:
                for tool_call in message["tool_calls"]:
                    tool_call["name"] = tool_call["function"]["name"]
                    tool_call["arguments"] = json.loads(
                        tool_call["function"]["arguments"]
                    )
            if message["role"] == "tool":
                message["content"] = {
                    "result": message["content"],
                    "call_id": message["tool_call_id"],
                }
        return payload

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Override the _generate method to implement the chat model logic.

        This can be a call to an API, a call to a local model, or any other
        implementation that generates a response to the input prompt.

        Args:
            messages: the prompt composed of a list of messages.
            stop: a list of strings on which the model should stop generating.
                  If generation stops due to a stop token, the stop token itself
                  SHOULD BE INCLUDED as part of the output. This is not enforced
                  across models right now, but it's a good practice to follow since
                  it makes it much easier to parse the output of the model
                  downstream and understand why generation stopped.
            run_manager: A run manager with callbacks for the LLM.
        """
        if kwargs.get("tools"):
            kwargs["tools"] = [tool["function"] for tool in kwargs["tools"]]
        if "tool_choice" in kwargs and kwargs["tool_choice"]["type"] == "function":
            kwargs["tool_choice"] = {
                "type": "tool",
                "name": kwargs["tool_choice"]["function"]["name"],
            }
        payload = self._get_request_payload(messages, stop=stop, **kwargs)

        response = self._call(self.url, payload, self.auth_headers)
        return self._create_chat_result(response)

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Override the _generate method to implement the chat model logic.

        This can be a call to an API, a call to a local model, or any other
        implementation that generates a response to the input prompt.

        Args:
            messages: the prompt composed of a list of messages.
            stop: a list of strings on which the model should stop generating.
                  If generation stops due to a stop token, the stop token itself
                  SHOULD BE INCLUDED as part of the output. This is not enforced
                  across models right now, but it's a good practice to follow since
                  it makes it much easier to parse the output of the model
                  downstream and understand why generation stopped.
            run_manager: A run manager with callbacks for the LLM.
        """
        if kwargs.get("tools"):
            kwargs["tools"] = [tool["function"] for tool in kwargs["tools"]]
        if "tool_choice" in kwargs and kwargs["tool_choice"]["type"] == "function":
            kwargs["tool_choice"] = {
                "type": "tool",
                "name": kwargs["tool_choice"]["function"]["name"],
            }
        payload = self._get_request_payload(messages, stop=stop, **kwargs)

        response = await self._acall(self.url, payload, self.auth_headers)
        return self._create_chat_result(response)

    def with_structured_output(
        self,
        schema: Optional[Any] = None,
        *,
        method: Literal[
            "function_calling", "json_mode", "json_schema"
        ] = "function_calling",
        include_raw: bool = False,
        strict: Optional[bool] = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, Any]:
        """Model wrapper that returns outputs formatted to match the given schema."""
        if method == "json_schema" and (
            not self.model_name or not self.model_name.startswith("gpt")
        ):
            method = "function_calling"
            if self.logger:
                self.logger.warning(
                    "The json_schema output is not supported for non-GPT models. Using function_calling instead.",
                    extra={
                        "ActionName": self.settings.action_name,
                        "ActionId": self.settings.action_id,
                    }
                    if self.settings
                    else None,
                )
        schema = (
            schema.model_json_schema()
            if isinstance(schema, type) and issubclass(schema, BaseModel)
            else schema
        )
        return super().with_structured_output(
            schema=schema,
            method=method,
            include_raw=include_raw,
            strict=strict,
            **kwargs,
        )

    @property
    def endpoint(self) -> str:
        return UiPathEndpoints.NORMALIZED_COMPLETION_ENDPOINT.value

    @property
    def is_normalized(self) -> bool:
        return True
