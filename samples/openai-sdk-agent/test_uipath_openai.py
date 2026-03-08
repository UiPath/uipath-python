#!/usr/bin/env python3
"""Test script to verify UiPath's OpenAI-compatible LLM Gateway."""

import os

from openai import OpenAI

try:
    import dotenv

    dotenv.load_dotenv()
except ImportError:
    pass  # dotenv not available, use environment variables directly

# Configure for UiPath
base_url = os.getenv("UIPATH_URL", "https://cloud.uipath.com")
access_token = os.getenv("UIPATH_ACCESS_TOKEN")

if not access_token:
    print("❌ UIPATH_ACCESS_TOKEN not set in environment")
    exit(1)

# Create OpenAI client pointing to UiPath
openai_base_url = f"{base_url.rstrip('/')}/orchestrator_/llm/openai"
print(f"Testing UiPath LLM Gateway at: {openai_base_url}")

client = OpenAI(
    api_key=access_token,
    base_url=openai_base_url,
)

# Test 1: List available models
print("\n1. Testing: List Models")
print("-" * 50)
try:
    models = client.models.list()
    print("✓ Success! Available models:")
    for model in models.data:
        print(f"  - {model.id}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 2: Simple chat completion
print("\n2. Testing: Chat Completion")
print("-" * 50)
try:
    response = client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[
            {"role": "user", "content": "Say 'Hello from UiPath!' and nothing else."}
        ],
        max_tokens=50,
    )
    print(f"✓ Success! Response: {response.choices[0].message.content}")
    print(f"  Model used: {response.model}")
    print(f"  Tokens: {response.usage.total_tokens}")
except Exception as e:
    print(f"❌ Error: {e}")

# Test 3: Chat completion with tool calling
print("\n3. Testing: Tool Calling")
print("-" * 50)
try:
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"}
                    },
                    "required": ["location"],
                },
            },
        }
    ]

    response = client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[{"role": "user", "content": "What's the weather in London?"}],
        tools=tools,
        max_tokens=100,
    )

    if response.choices[0].message.tool_calls:
        print("✓ Success! Tool was called:")
        for tool_call in response.choices[0].message.tool_calls:
            print(f"  - Function: {tool_call.function.name}")
            print(f"  - Arguments: {tool_call.function.arguments}")
    else:
        print(f"⚠ No tool calls. Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n" + "=" * 50)
print("UiPath OpenAI LLM Gateway Test Complete")
print("=" * 50)
