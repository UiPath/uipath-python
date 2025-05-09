from contextlib import asynccontextmanager
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
import dotenv
import os

dotenv.load_dotenv()


@asynccontextmanager
async def make_graph():
    async with MultiServerMCPClient() as client:
        await client.connect_to_server_via_sse(
            server_name="hello-world-server",
            url=os.getenv("UIPATH_MCP_SERVER_URL"),
            headers={
                "Authorization": f"Bearer {os.getenv('UIPATH_ACCESS_TOKEN')}"
                },
            timeout=60,
        )

        tools = client.get_tools()
        print(tools)
        model = ChatAnthropic(model="claude-3-5-sonnet-latest")
        graph = create_react_agent(model, tools=tools)
        yield graph
