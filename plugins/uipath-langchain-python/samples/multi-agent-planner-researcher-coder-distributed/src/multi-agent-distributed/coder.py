from typing import Annotated

from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

llm = ChatAnthropic(model="claude-3-5-sonnet-latest")

repl = PythonREPL()


class GraphOutput(BaseModel):
    answer: str


@tool
def python_repl_tool(
    code: Annotated[str, "The python code to execute to generate your chart."],
):
    """Use this to execute python code and do math. If you want to see the output of a value,
    you should print it out with `print(...)`. This is visible to the user.
    """
    try:
        result = repl.run(code)
    except BaseException as e:
        return f"Failed to execute. Error: {repr(e)}"
    result_str = (
        f"Successfully executed:\n\`\`\`python\n{code}\n\`\`\`\nStdout: {result}"
    )
    return result_str


code_agent = create_react_agent(llm, tools=[python_repl_tool])


async def code_node(state: MessagesState) -> GraphOutput:
    result = await code_agent.ainvoke(state)
    return GraphOutput(answer=result["messages"][-1].content)


# Build the state graph
builder = StateGraph(MessagesState, output=GraphOutput)
builder.add_node("coder", code_node)

builder.add_edge(START, "coder")
builder.add_edge("coder", END)

# Compile the graph
graph = builder.compile()
