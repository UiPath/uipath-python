"""Define a custom Reasoning and Action agent.

Works with a chat model with tool calling support.
"""
from datetime import datetime, timezone
from pprint import pprint
from typing import Literal, cast

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.prebuilt import ToolNode

from configuration import Configuration
from state import InputState, State, OutputState
from supplier_website_reader import SupplierWebsiteReader
from uipath_ecs_retriever_tool import retriever_tool
from utils import load_chat_model
from pydantic import BaseModel

TOOLS = [ SupplierWebsiteReader, retriever_tool ]


def input_node(state: State, config: RunnableConfig):

    configuration = Configuration.from_runnable_config(config)

    # Format the user prompt. Customize this to change the agent's behavior.
    user_message = configuration.user_prompt.format(
        MismatchedItems=state.MismatchedItems,
        SupplierWebsite=state.SupplierWebsite,
        Supplier=state.Supplier,
        Company=state.Company
    )
    state.messages.append(HumanMessage(user_message))

# We are going "bind" all tools to the model
# We have the ACTUAL tools from above, but we also need a mock tool to ask a human
# Since `bind_tools` takes in tools but also just tool definitions,
# We can define a tool definition for `ask_human`
class AskHuman(BaseModel):
    """Ask the human a question"""

    question: str

def call_model(
    state: State, config: RunnableConfig
) -> State:
    """Call the LLM powering our "agent".

    This function prepares the prompt, initializes the model, and processes the response.

    Args:
        state (State): The current state of the conversation.
        config (RunnableConfig): Configuration for the model run.

    Returns:
        dict: A dictionary containing the model's response message.
    """

    configuration = Configuration.from_runnable_config(config)

    # Initialize the model with tool binding. Change the model or add more tools here.

    model = load_chat_model(configuration.model).bind_tools(TOOLS + [AskHuman])

    # Format the system prompt. Customize this to change the agent's behavior.
    system_message = configuration.system_prompt.format(
        system_time=datetime.now(tz=timezone.utc).isoformat(),
    )

    # Get the model's response
    response = cast(
        AIMessage,
        model.invoke(
            [{"role": "system", "content": system_message}, *state.messages], config
        ),
    )

    # Handle the case when it's the last step and the model still wants to use a tool
    if state.is_last_step and response.tool_calls:
        response = AIMessage(
                    id=response.id,
                    content="Sorry, I could not find an answer to your question in the specified number of steps.",
                )
    else:
        state.SupplierEmail="supplier@acme.company"
        state.InvestigationResult="The results are in"

    state.messages.append(response)

    # Return the model's response as a list to be added to existing messages
    return state # {"messages": [response]}

def output_node(state: State, config: RunnableConfig) -> OutputState:
    configuration = Configuration.from_runnable_config(config)

    # Initialize the model with tool binding. Change the model or add more tools here.

    model = load_chat_model(configuration.model).with_structured_output(OutputState)

    pprint(state)

    response = cast(
        OutputState,
        model.invoke(
            [{"role": "system", "content": "Build the output message"}, *state.messages], config
        ),
    )

    return response

# We define a fake node to ask the human
def ask_human(state: State):
    tool_call_id = state.messages[-1].tool_calls[0]["id"]
    tool_message = [{"tool_call_id": tool_call_id, "type": "tool", "content": "Human call is not implemented"}]
    return {"messages": tool_message}

# Define a new graph

builder = StateGraph(State, input=InputState, output=OutputState, config_schema=Configuration)

builder.add_node(input_node)

# Define the two nodes we will cycle between
builder.add_node(call_model)
builder.add_node("tools", ToolNode(TOOLS))
builder.add_node("ask_human", ask_human)
builder.add_node(output_node)

# Set the entrypoint as `call_model`
# This means that this node is the first one called
builder.add_edge("__start__", "input_node")
builder.add_edge("input_node", "call_model")
builder.add_edge("output_node", "__end__")


def route_model_output(state: State) -> Literal["output_node", "tools", "ask_human"]:
    """Determine the next node based on the model's output.

    This function checks if the model's last message contains tool calls.

    Args:
        state (State): The current state of the conversation.

    Returns:
        str: The name of the next node to call ("output_node" or "tools" or "ask_human").
    """

    last_message = state.messages[-1]
    if not isinstance(last_message, AIMessage):
        raise ValueError(
            f"Expected AIMessage in output edges, but got {type(last_message).__name__}"
        )
    # If there is no tool call, then we finish
    if not last_message.tool_calls:
        return "output_node"

    if last_message.tool_calls[0]["name"] == "AskHuman":
        return "ask_human"

    # Otherwise we execute the requested actions
    return "tools"

# Add a conditional edge to determine the next step after `call_model`
builder.add_conditional_edges(
    "call_model",
    # After call_model finishes running, the next node(s) are scheduled
    # based on the output from route_model_output
    route_model_output,
)

# Add a normal edge from `tools` to `call_model`
# This creates a cycle: after using tools, we always return to the model
builder.add_edge("tools", "call_model")
builder.add_edge("ask_human", "call_model")

# Compile the builder into an executable graph
# You can customize this by adding interrupt points for state updates
graph = builder.compile(
    interrupt_before=[],  # Add node names here to update state before they're called
    interrupt_after=[],  # Add node names here to update state after they're called
)
graph.name = "Invoice Dispute Investigation Agent"  # This customizes the name in LangSmith
