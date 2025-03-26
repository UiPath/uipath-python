import os
import sys
from contextlib import asynccontextmanager

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel
from uipath_langchain.chat.models import (
    UiPathNormalizedChatModel,
)


class GraphInput(BaseModel):
    message: str


class GraphOutput(BaseModel):
    summary: str


def get_file_path(filename):
    """Get absolute path to file in current directory."""
    return os.path.abspath(os.path.join(os.getcwd(), filename))


mcp_config = {
    "travel_mcp": {
        "command": sys.executable,
        "args": [get_file_path("./mcps/travel_mcp.py")],
        "transport": "stdio",
    }
}


@asynccontextmanager
async def make_graph():
    async with MultiServerMCPClient(mcp_config) as client:
        tools = client.get_tools()
        tool_node = ToolNode(tools)

        def init(state: GraphInput):
            return {
                "messages": [
                    SystemMessage(
                        content="You are a helpful travel planner assistant!. When you are done please write your report in markdown as a single message and begin with `# Final Report`"
                    ),
                    HumanMessage(content=state.message),
                ]
            }

        def should_continue(state: MessagesState):
            messages = state["messages"]
            last_message = messages[-1]

            # Check if the last message contains a final report indicator
            if hasattr(last_message, "content") and isinstance(
                last_message.content, str
            ):
                if "# final report" in last_message.content.lower():
                    return "output_summary"

            if last_message.tool_calls:
                return "tools"

            return "agent"

        def output_summary(state: MessagesState):
            messages = state["messages"]
            last_message = messages[-1]
            return {"summary": last_message.content}

        async def call_model(state: MessagesState):
            messages = state["messages"]

            agent = UiPathNormalizedChatModel().bind_tools(tools)
            response = agent.invoke(messages)

            return {"messages": [response]}

        workflow = StateGraph(MessagesState, input=GraphInput, output=GraphOutput)
        # workflow = StateGraph(MessagesState)

        # Define the two nodes we will cycle between
        workflow.add_node("init", init)
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", tool_node)
        workflow.add_node("output_summary", output_summary)

        workflow.add_edge(START, "init")
        workflow.add_edge("init", "agent")
        workflow.add_conditional_edges(
            "agent", should_continue, ["tools", "output_summary", "agent"]
        )
        workflow.add_edge("tools", "agent")
        workflow.add_edge("output_summary", END)

        graph = workflow.compile()

        yield graph
