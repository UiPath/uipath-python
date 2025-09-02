"""Tests for LangchainSpanProcessor."""

import json
from platform import processor

import pytest

from uipath.tracing._otel_exporters import CommonSpanProcessor

processor = CommonSpanProcessor()


class TestUnflattenDict:
    """Test the unflatten_dict utility function."""

    def test_simple_unflatten(self):
        """Test basic unflattening functionality."""
        flat_dict = {"user.name": "John", "user.age": 30, "settings.theme": "dark"}

        result = processor.unflatten_dict(flat_dict)

        assert result == {
            "user": {"name": "John", "age": 30},
            "settings": {"theme": "dark"},
        }

    def test_array_unflatten(self):
        """Test unflattening with array indices."""
        flat_dict = {
            "items.0.name": "first",
            "items.0.value": 1,
            "items.1.name": "second",
            "items.1.value": 2,
        }

        result = processor.unflatten_dict(flat_dict)

        expected = {
            "items": [{"name": "first", "value": 1}, {"name": "second", "value": 2}]
        }
        assert result == expected

    def test_nested_arrays(self):
        """Test deeply nested structures with arrays."""
        flat_dict = {
            "llm.messages.0.content": "hello",
            "llm.messages.0.tools.0.name": "tool1",
            "llm.messages.0.tools.1.name": "tool2",
            "llm.provider": "azure",
        }

        result = processor.unflatten_dict(flat_dict)

        expected = {
            "llm": {
                "messages": [
                    {
                        "content": "hello",
                        "tools": [{"name": "tool1"}, {"name": "tool2"}],
                    }
                ],
                "provider": "azure",
            }
        }
        assert result == expected

    def test_sparse_arrays(self):
        """Test arrays with gaps in indices."""
        flat_dict = {"items.0.name": "first", "items.2.name": "third"}

        result = processor.unflatten_dict(flat_dict)

        expected = {"items": [{"name": "first"}, None, {"name": "third"}]}
        assert result == expected

    def test_empty_dict(self):
        """Test with empty dictionary."""
        result = processor.unflatten_dict({})
        assert result == {}

    def test_single_level_keys(self):
        """Test with keys that don't need unflattening."""
        flat_dict = {"name": "value", "number": 42}
        result = processor.unflatten_dict(flat_dict)
        assert result == flat_dict


class TestLangchainSpanProcessor:
    """Test the LangchainSpanProcessor class."""

    def test_init_defaults(self):
        """Test initialization with default parameters."""
        processor = CommonSpanProcessor()
        assert processor._dump_attributes_as_string is True
        assert processor._unflatten_attributes is True

    def test_init_custom_params(self):
        """Test initialization with custom parameters."""
        processor = CommonSpanProcessor(
            dump_attributes_as_string=False, unflatten_attributes=True
        )
        assert processor._dump_attributes_as_string is False
        assert processor._unflatten_attributes is True

    def test_process_span_without_attributes(self):
        """Test processing span without attributes."""
        processor = CommonSpanProcessor()
        span_data = {"Id": "test-id", "Name": "TestSpan"}

        result = processor.process_span(span_data)
        assert result == span_data

    def test_process_span_with_unflatten_disabled(self):
        """Test processing span with unflattening disabled."""
        processor = CommonSpanProcessor(
            dump_attributes_as_string=False, unflatten_attributes=False
        )

        attributes = {
            "llm.output_messages.0.role": "assistant",
            "llm.provider": "azure",
            "model": "gpt-4",
        }

        span_data = {"Id": "test-id", "Attributes": json.dumps(attributes)}

        result = processor.process_span(span_data)

        # Should keep flattened structure
        assert result["attributes"]["llm.output_messages.0.role"] == "assistant"
        assert result["attributes"]["llm.provider"] == "azure"
        assert result["attributes"]["model"] == "gpt-4"

    def test_process_span_with_unflatten_and_json_output(self):
        """Test processing span with unflattening and JSON string output."""
        processor = CommonSpanProcessor(
            dump_attributes_as_string=True, unflatten_attributes=True
        )

        attributes = {"llm.provider": "azure", "llm.messages.0.role": "user"}

        span_data = {"Id": "test-id", "Attributes": json.dumps(attributes)}

        result = processor.process_span(span_data)

        # Should be JSON string
        assert isinstance(result["attributes"], str)

        # Parse and verify nested structure
        parsed = json.loads(result["attributes"])
        assert parsed["llm"]["provider"] == "azure"
        assert parsed["llm"]["messages"][0]["role"] == "user"

    def test_token_usage_processing_with_unflatten(self):
        """Test token usage processing with unflattening."""
        processor = CommonSpanProcessor(
            dump_attributes_as_string=False, unflatten_attributes=True
        )

        attributes = {
            "llm.token_count.prompt": 100,
            "llm.token_count.completion": 50,
            "llm.token_count.total": 150,
            "llm.provider": "azure",
        }

        span_data = {"Id": "test-id", "Attributes": json.dumps(attributes)}

        result = processor.process_span(span_data)
        attrs = result["attributes"]

        # Check usage structure
        assert attrs["usage"]["promptTokens"] == 100
        assert attrs["usage"]["completionTokens"] == 50
        assert attrs["usage"]["totalTokens"] == 150
        assert attrs["usage"]["isByoExecution"] is False

        # Check unflattening of other attributes
        assert attrs["llm"]["provider"] == "azure"

    def test_unflatten_error_handling(self):
        """Test error handling in unflattening."""
        processor = CommonSpanProcessor(
            dump_attributes_as_string=False, unflatten_attributes=True
        )

        # Create a scenario that might cause unflattening issues
        # This should be handled gracefully
        attributes = {"normal.key": "value", "llm.provider": "azure"}

        span_data = {"Id": "test-id", "Attributes": json.dumps(attributes)}

        # Should not raise an exception
        result = processor.process_span(span_data)
        assert "attributes" in result

    def test_process_span_with_dict_attributes_unflatten_enabled(self):
        """Test processing span with dictionary attributes and unflattening enabled."""
        processor = CommonSpanProcessor(
            dump_attributes_as_string=False, unflatten_attributes=True
        )

        # Simulate the real-world case where Attributes is already a dictionary
        attributes = {
            "llm.output_messages.0.message.role": "assistant",
            "llm.output_messages.0.message.tool_calls.0.tool_call.id": "call_123",
            "llm.output_messages.0.message.tool_calls.0.tool_call.function.name": "get_time",
            "llm.provider": "azure",
            "model": "gpt-4",
        }

        span_data = {
            "Id": "test-id",
            "Attributes": attributes,  # Already a dictionary, not a JSON string
        }

        result = processor.process_span(span_data)

        # Should have nested structure
        attrs = result["attributes"]
        assert attrs["llm"]["output_messages"][0]["message"]["role"] == "assistant"
        assert (
            attrs["llm"]["output_messages"][0]["message"]["tool_calls"][0]["tool_call"][
                "id"
            ]
            == "call_123"
        )
        assert (
            attrs["llm"]["output_messages"][0]["message"]["tool_calls"][0]["tool_call"][
                "function"
            ]["name"]
            == "get_time"
        )
        assert attrs["llm"]["provider"] == "azure"

    def test_real_world_trace_unflatten(self):
        """Test with real-world trace data to verify unflattening works correctly."""
        processor = CommonSpanProcessor(
            dump_attributes_as_string=False, unflatten_attributes=True
        )

        # Real trace data from user's example (dictionary format)
        real_trace_attributes = {
            "input.mime_type": "application/json",
            "output.mime_type": "application/json",
            "llm.input_messages.0.message.role": "user",
            "llm.input_messages.0.message.content": "You are a helpful assistant with access to various tools. \n    The user is asking about: Weather and Technology\n    \n    Please use the available tools to gather some relevant information. For example:\n    - Check the current time\n    - Generate a random number if relevant\n    - Calculate squares of numbers if needed\n    - Get weather information for any cities mentioned\n    \n    Use at least 2-3 tools to demonstrate their functionality.",
            "llm.output_messages.0.message.role": "assistant",
            "llm.output_messages.0.message.tool_calls.0.tool_call.id": "call_qWaFnNRY8mk2PQjEu0wRLaRd",
            "llm.output_messages.0.message.tool_calls.0.tool_call.function.name": "get_current_time",
            "llm.output_messages.0.message.tool_calls.1.tool_call.id": "call_3ckaPILSv4SmyeufQf1ovA3H",
            "llm.output_messages.0.message.tool_calls.1.tool_call.function.name": "generate_random_number",
            "llm.output_messages.0.message.tool_calls.1.tool_call.function.arguments": '{"min_val": 1, "max_val": 10}',
            "llm.output_messages.0.message.tool_calls.2.tool_call.id": "call_BjaiJ0NHwWs14fMbCyjDElEX",
            "llm.output_messages.0.message.tool_calls.2.tool_call.function.name": "get_weather_info",
            "llm.output_messages.0.message.tool_calls.2.tool_call.function.arguments": '{"city": "San Francisco"}',
            "llm.invocation_parameters": '{"model": "gpt-4o-mini-2024-07-18", "url": "https://alpha.uipath.com/..."}',
            "llm.tools.0.tool.json_schema": '{"type": "function", "function": {"name": "get_current_time", "description": "Get the current date and time.", "parameters": {"properties": {}, "type": "object"}}}',
            "llm.tools.1.tool.json_schema": '{"type": "function", "function": {"name": "generate_random_number", "description": "Generate a random number between min_val and max_val (inclusive).", "parameters": {"properties": {"min_val": {"default": 1, "type": "integer"}, "max_val": {"default": 100, "type": "integer"}}, "type": "object"}}}',
            "llm.tools.2.tool.json_schema": '{"type": "function", "function": {"name": "calculate_square", "description": "Calculate the square of a given number.", "parameters": {"properties": {"number": {"type": "number"}}, "required": ["number"], "type": "object"}}}',
            "llm.tools.3.tool.json_schema": '{"type": "function", "function": {"name": "get_weather_info", "description": "Get mock weather information for a given city.", "parameters": {"properties": {"city": {"type": "string"}}, "required": ["city"], "type": "object"}}}',
            "llm.provider": "azure",
            "llm.system": "openai",
            "session.id": "a879985a-8d39-4f51-94e1-8433423f35db",
            "metadata": '{"thread_id": "a879985a-8d39-4f51-94e1-8433423f35db", "langgraph_step": 1, "langgraph_node": "make_tool_calls"}',
            "model": "gpt-4o-mini-2024-07-18",
            "usage": {
                "promptTokens": 219,
                "completionTokens": 66,
                "totalTokens": 285,
                "isByoExecution": False,
            },
        }

        span_data = {
            "PermissionStatus": 0,
            "Id": "7d137190-348c-4ef2-9b19-165295643b82",
            "TraceId": "81dbeaf2-c2ba-4b1e-95fd-b722f53dc405",
            "ParentId": "f71478d6-f081-4bf6-a942-0944d97ffadb",
            "Name": "UiPathChat",
            "StartTime": "2025-08-26T16:11:17.276Z",
            "EndTime": "2025-08-26T16:11:20.027Z",
            "Attributes": real_trace_attributes,  # Dictionary format (not JSON string)
            "SpanType": "completion",
        }

        # Process the span
        result = processor.process_span(span_data)

        # Verify the trace data structure is preserved
        assert result["Id"] == "7d137190-348c-4ef2-9b19-165295643b82"
        assert result["Name"] == "UiPathChat"
        assert result["SpanType"] == "completion"

        # Verify attributes are unflattened and accessible
        attrs = result["attributes"]
        assert isinstance(attrs, dict)

        # Test LLM provider info
        assert attrs["llm"]["provider"] == "azure"
        assert attrs["llm"]["system"] == "openai"

        # Test input messages
        input_messages = attrs["llm"]["input_messages"]
        assert len(input_messages) == 1
        assert input_messages[0]["message"]["role"] == "user"
        assert "helpful assistant" in input_messages[0]["message"]["content"]

        # Test output messages and tool calls
        output_messages = attrs["llm"]["output_messages"]
        assert len(output_messages) == 1
        assert output_messages[0]["message"]["role"] == "assistant"

        tool_calls = output_messages[0]["message"]["tool_calls"]
        assert len(tool_calls) == 3

        # Verify individual tool calls
        assert tool_calls[0]["tool_call"]["function"]["name"] == "get_current_time"
        assert tool_calls[0]["tool_call"]["id"] == "call_qWaFnNRY8mk2PQjEu0wRLaRd"

        assert (
            tool_calls[1]["tool_call"]["function"]["name"] == "generate_random_number"
        )

        assert tool_calls[2]["tool_call"]["function"]["name"] == "get_weather_info"
        # Test tools schema
        tools = attrs["llm"]["tools"]
        assert len(tools) == 4

        # Test session data
        assert attrs["session"]["id"] == "a879985a-8d39-4f51-94e1-8433423f35db"

    def test_invalid_json_attributes(self):
        """Test handling of invalid JSON in attributes."""
        processor = CommonSpanProcessor(unflatten_attributes=True)

        span_data = {"Id": "test-id", "Attributes": "invalid json {"}

        # Should handle gracefully and return original span
        # Note: invalid JSON causes the Attributes key to be removed
        result = processor.process_span(span_data)
        assert result["Id"] == "test-id"
        assert "Attributes" not in result  # Attributes key is removed on invalid JSON

    def test_process_span_with_provided_json(self):
        """Test processing a span with the user-provided JSON data."""
        # Test with default settings (unflatten=True, dump_as_string=True)
        processor = CommonSpanProcessor()

        input_data = {
            "Id": "f4b31bcb-caaa-4979-8a33-099ef4eed977",
            "TraceId": "8164a1dd-fb29-42fd-b49a-afdccafe486e",
            "ParentId": "8d82c004-bb59-497b-b290-ab02b3699543",
            "Name": "UiPathChat",
            "StartTime": "2025-08-28T15:10:39.972276",
            "EndTime": "2025-08-28T15:10:42.270506",
            "Attributes": '{"input.value": "{\\"messages\\": [[{\\"lc\\": 1, \\"type\\": \\"constructor\\", \\"id\\": [\\"langchain\\", \\"schema\\", \\"messages\\", \\"HumanMessage\\"], \\"kwargs\\": {\\"content\\": \\"You are a helpful assistant with access to various tools. \\\\n    The user is asking about: Weather and Technology\\\\n    \\\\n    Please use the available tools to gather some relevant information. For example:\\\\n    - Check the current time\\\\n    - Generate a random number if relevant\\\\n    - Calculate squares of numbers if needed\\\\n    - Get weather information for any cities mentioned\\\\n    \\\\n    Use at least 2-3 tools to demonstrate their functionality.\\", \\"type\\": \\"human\\"}}]]}", "input.mime_type": "application/json", "output.value": "{\\"generations\\": [[{\\"text\\": \\"\\", \\"generation_info\\": null, \\"type\\": \\"ChatGeneration\\", \\"message\\": {\\"lc\\": 1, \\"type\\": \\"constructor\\", \\"id\\": [\\"langchain\\", \\"schema\\", \\"messages\\", \\"AIMessage\\"], \\"kwargs\\": {\\"content\\": \\"\\", \\"response_metadata\\": {\\"token_usage\\": {\\"completion_tokens\\": 66, \\"prompt_tokens\\": 219, \\"total_tokens\\": 285, \\"cache_read_input_tokens\\": 0}, \\"model_name\\": \\"gpt-4o-mini-2024-07-18\\", \\"finish_reason\\": \\"tool_calls\\", \\"system_fingerprint\\": \\"chatcmpl-C9YYq3MkM9laikeNVJ72xJJvYmWsO\\", \\"created\\": 1756393840}, \\"type\\": \\"ai\\", \\"id\\": \\"run--70aec293-656e-4dcb-a253-8317bdda4295-0\\", \\"tool_calls\\": [{\\"id\\": \\"call_kqqmcYwjzusMABpJC5nQJJM6\\", \\"name\\": \\"get_current_time\\", \\"args\\": {}, \\"type\\": \\"tool_call\\"}, {\\"id\\": \\"call_RsgILurSpogORi2FBPXLfTju\\", \\"name\\": \\"generate_random_number\\", \\"args\\": {\\"min_val\\": 1, \\"max_val\\": 10}, \\"type\\": \\"tool_call\\"}, {\\"id\\": \\"call_BgBqVNMqIzL151D12rMLW4Dg\\", \\"name\\": \\"get_weather_info\\", \\"args\\": {\\"city\\": \\"New York\\"}, \\"type\\": \\"tool_call\\"}], \\"usage_metadata\\": {\\"input_tokens\\": 219, \\"output_tokens\\": 66, \\"total_tokens\\": 285}, \\"invalid_tool_calls\\": []}}}]], \\"llm_output\\": null, \\"run\\": null, \\"type\\": \\"LLMResult\\"}", "output.mime_type": "application/json", "llm.input_messages.0.message.role": "user", "llm.input_messages.0.message.content": "You are a helpful assistant with access to various tools. \\n    The user is asking about: Weather and Technology\\n    \\n    Please use the available tools to gather some relevant information. For example:\\n    - Check the current time\\n    - Generate a random number if relevant\\n    - Calculate squares of numbers if needed\\n    - Get weather information for any cities mentioned\\n    \\n    Use at least 2-3 tools to demonstrate their functionality.", "llm.output_messages.0.message.role": "assistant", "llm.output_messages.0.message.tool_calls.0.tool_call.id": "call_kqqmcYwjzusMABpJC5nQJJM6", "llm.output_messages.0.message.tool_calls.0.tool_call.function.name": "get_current_time", "llm.output_messages.0.message.tool_calls.1.tool_call.id": "call_RsgILurSpogORi2FBPXLfTju", "llm.output_messages.0.message.tool_calls.1.tool_call.function.name": "generate_random_number", "llm.output_messages.0.message.tool_calls.1.tool_call.function.arguments": "{\\"min_val\\": 1, \\"max_val\\": 10}", "llm.output_messages.0.message.tool_calls.2.tool_call.id": "call_BgBqVNMqIzL151D12rMLW4Dg", "llm.output_messages.0.message.tool_calls.2.tool_call.function.name": "get_weather_info", "llm.output_messages.0.message.tool_calls.2.tool_call.function.arguments": "{\\"city\\": \\"New York\\"}", "llm.invocation_parameters": "{\\"model\\": \\"gpt-4o-mini-2024-07-18\\", \\"url\\": \\"https://alpha.uipath.com/b7006b1c-11c3-4a80-802e-fee0ebf9c360/6961a069-3392-40ca-bf5d-276f4e54c8ff/agenthub_/llm/api/chat/completions\\", \\"temperature\\": 0.0, \\"max_tokens\\": 1000, \\"frequency_penalty\\": null, \\"presence_penalty\\": null, \\"_type\\": \\"uipath\\", \\"stop\\": null, \\"stream\\": false, \\"tools\\": [{\\"type\\": \\"function\\", \\"function\\": {\\"name\\": \\"get_current_time\\", \\"description\\": \\"Get the current date and time.\\", \\"parameters\\": {\\"properties\\": {}, \\"type\\": \\"object\\"}}}, {\\"type\\": \\"function\\", \\"function\\": {\\"name\\": \\"generate_random_number\\", \\"description\\": \\"Generate a random number between min_val and max_val (inclusive).\\", \\"parameters\\": {\\"properties\\": {\\"min_val\\": {\\"default\\": 1, \\"type\\": \\"integer\\"}, \\"max_val\\": {\\"default\\": 100, \\"type\\": \\"integer\\"}}, \\"type\\": \\"object\\"}}}, {\\"type\\": \\"function\\", \\"function\\": {\\"name\\": \\"calculate_square\\", \\"description\\": \\"Calculate the square of a given number.\\", \\"parameters\\": {\\"properties\\": {\\"number\\": {\\"type\\": \\"number\\"}}, \\"required\\": [\\"number\\"], \\"type\\": \\"object\\"}}}, {\\"type\\": \\"function\\", \\"function\\": {\\"name\\": \\"get_weather_info\\", \\"description\\": \\"Get mock weather information for a given city.\\", \\"parameters\\": {\\"properties\\": {\\"city\\": {\\"type\\": \\"string\\"}}, \\"required\\": [\\"city\\"], \\"type\\": \\"object\\"}}}]}", "llm.tools.0.tool.json_schema": "{\\"type\\": \\"function\\", \\"function\\": {\\"name\\": \\"get_current_time\\", \\"description\\": \\"Get the current date and time.\\", \\"parameters\\": {\\"properties\\": {}, \\"type\\": \\"object\\"}}}", "llm.tools.1.tool.json_schema": "{\\"type\\": \\"function\\", \\"function\\": {\\"name\\": \\"generate_random_number\\", \\"description\\": \\"Generate a random number between min_val and max_val (inclusive).\\", \\"parameters\\": {\\"properties\\": {\\"min_val\\": {\\"default\\": 1, \\"type\\": \\"integer\\"}, \\"max_val\\": {\\"default\\": 100, \\"type\\": \\"integer\\"}}, \\"type\\": \\"object\\"}}}", "llm.tools.2.tool.json_schema": "{\\"type\\": \\"function\\", \\"function\\": {\\"name\\": \\"calculate_square\\", \\"description\\": \\"Calculate the square of a given number.\\", \\"parameters\\": {\\"properties\\": {\\"number\\": {\\"type\\": \\"number\\"}}, \\"required\\": [\\"number\\"], \\"type\\": \\"object\\"}}}", "llm.tools.3.tool.json_schema": "{\\"type\\": \\"function\\", \\"function\\": {\\"name\\": \\"get_weather_info\\", \\"description\\": \\"Get mock weather information for a given city.\\", \\"parameters\\": {\\"properties\\": {\\"city\\": {\\"type\\": \\"string\\"}}, \\"required\\": [\\"city\\"], \\"type\\": \\"object\\"}}}", "llm.provider": "azure", "llm.system": "openai", "llm.model_name": "gpt-4o-mini-2024-07-18", "llm.token_count.prompt": 219, "llm.token_count.completion": 66, "llm.token_count.total": 285, "session.id": "2d619d5e-528d-4219-a166-971414eec294", "metadata": "{\\"thread_id\\": \\"2d619d5e-528d-4219-a166-971414eec294\\", \\"langgraph_step\\": 1, \\"langgraph_node\\": \\"make_tool_calls\\", \\"langgraph_triggers\\": [\\"branch:to:make_tool_calls\\"], \\"langgraph_path\\": [\\"__pregel_pull\\", \\"make_tool_calls\\"], \\"langgraph_checkpoint_ns\\": \\"make_tool_calls:e564e2fb-32d5-3cfa-9bb0-53679afa5af0\\", \\"checkpoint_ns\\": \\"make_tool_calls:e564e2fb-32d5-3cfa-9bb0-53679afa5af0\\", \\"ls_provider\\": \\"azure\\", \\"ls_model_name\\": \\"gpt-4o-mini-2024-07-18\\", \\"ls_model_type\\": \\"chat\\", \\"ls_temperature\\": 0.0, \\"ls_max_tokens\\": 1000}", "openinference.span.kind": "LLM"}',
            "Status": 1,
            "CreatedAt": "2025-08-28T15:10:43.580667Z",
            "UpdatedAt": "2025-08-28T15:10:43.580670Z",
            "OrganizationId": "b7006b1c-11c3-4a80-802e-fee0ebf9c360",
            "TenantId": "6961a069-3392-40ca-bf5d-276f4e54c8ff",
            "ExpiryTimeUtc": None,
            "FolderKey": "d0e72980-7a97-44e1-93b7-4087689521b7",
            "Source": None,
            "SpanType": "OpenTelemetry",
            "ProcessKey": "65965c09-87e3-4fa3-a7be-3fdb3955bd47",
            "JobKey": "2d619d5e-528d-4219-a166-971414eec294",
        }

        result = processor.process_span(input_data)

        # Assertions
        assert result["SpanType"] == "completion"
        assert isinstance(result["attributes"], str)

        attrs = json.loads(result["attributes"])

        # Check unflattening
        assert "llm" in attrs
        assert "input_messages" in attrs["llm"]
        assert "output_messages" in attrs["llm"]
        assert "invocation_parameters" in attrs["llm"]

        # Check attribute mapping
        assert "model" in attrs
        assert attrs["model"] == "gpt-4o-mini-2024-07-18"
        assert "input" in attrs
        assert "output" in attrs

        # Check JSON field mapping
        assert "usage" in attrs
        assert attrs["usage"]["promptTokens"] == 219
        assert attrs["usage"]["completionTokens"] == 66
        assert attrs["usage"]["totalTokens"] == 285

        assert "toolCalls" in attrs
        assert len(attrs["toolCalls"]) == 3
        assert attrs["toolCalls"][0]["name"] == "get_current_time"
        assert attrs["toolCalls"][1]["name"] == "generate_random_number"
        assert attrs["toolCalls"][2]["name"] == "get_weather_info"
        assert attrs["toolCalls"][2]["arguments"] == {"city": "New York"}

        assert "settings" in attrs
        assert attrs["settings"]["maxTokens"] == 1000
        assert attrs["settings"]["temperature"] == 0.0


# uipath-langchain==0.0.123.dev1001490444
