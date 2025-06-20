import dotenv
import os
from contextlib import asynccontextmanager
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.tools import load_mcp_tools
from mcp import ClientSession
from mcp.client.sse import sse_client

dotenv.load_dotenv()

@asynccontextmanager
async def make_graph():
    async with sse_client(
        url=os.getenv("UIPATH_MCP_SERVER_URL"),
        headers={"Authorization": f"Bearer {os.getenv('UIPATH_ACCESS_TOKEN')}"},
        timeout=60,
    ) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await load_mcp_tools(session)
            print(tools)
            model = ChatAnthropic(model="claude-3-5-sonnet-latest")
            agent = create_react_agent(model, tools=tools)
            yield agent
