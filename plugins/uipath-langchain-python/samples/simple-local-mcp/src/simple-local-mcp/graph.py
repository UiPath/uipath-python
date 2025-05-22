import sys
from contextlib import asynccontextmanager

from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

model = ChatAnthropic(model="claude-3-5-sonnet-latest")


@asynccontextmanager
async def make_graph():
    client = MultiServerMCPClient({
            "math": {
                "command": sys.executable,
                "args": ["src/simple-local-mcp/math_server.py"],
                "transport": "stdio",
            },
            "weather": {
                "command": sys.executable,
                "args": ["src/simple-local-mcp/weather_server.py"],
                "transport": "stdio",
            },
        })
    agent = create_react_agent(model, await client.get_tools())
    yield agent
