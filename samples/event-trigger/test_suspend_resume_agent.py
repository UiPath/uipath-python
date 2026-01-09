"""Test agent that demonstrates suspend/resume pattern with RPA process invocation."""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt
from pydantic import BaseModel

from uipath.platform.common import InvokeProcess


class Input(BaseModel):
    """Input for the test agent."""

    query: str


class Output(BaseModel):
    """Output from the test agent."""

    result: str
    process_output: dict | None = None


class State(TypedDict):
    """Agent state."""

    query: str
    process_result: dict | None
    final_result: str


def prepare_input(state: State) -> State:
    """Prepare input for RPA process."""
    print(f"Preparing to call RPA process with query: {state['query']}")
    return state


def call_rpa_process(state: State) -> State:
    """Call RPA process - this will suspend execution."""
    print("Calling RPA process - execution will suspend here")

    # This interrupt() call will cause the runtime to suspend
    # The serverless executor will detect SUSPENDED status, poll the job,
    # and then resume execution once the job completes
    process_result = interrupt(
        InvokeProcess(
            name="TestProcess",  # Replace with actual process name
            input_arguments={"query": state["query"], "timestamp": "2024-01-08"},
            process_folder_path="Shared",  # Replace with actual folder
            process_folder_key=None,
        )
    )

    print(f"RPA process completed with result: {process_result}")

    return {**state, "process_result": process_result}


def format_output(state: State) -> State:
    """Format final output after RPA process completes."""
    process_result = state.get("process_result", {})

    final_result = (
        f"Processed query '{state['query']}' via RPA. Result: {process_result}"
    )

    return {**state, "final_result": final_result}


# Build the graph
builder = StateGraph(State)
builder.add_node("prepare", prepare_input)
builder.add_node("call_rpa", call_rpa_process)
builder.add_node("format", format_output)

builder.add_edge(START, "prepare")
builder.add_edge("prepare", "call_rpa")
builder.add_edge("call_rpa", "format")
builder.add_edge("format", END)


def main(input_data: Input):
    """Main entry point for the agent.

    Returns raw dict to preserve __interrupt__ field for suspend/resume.
    When execution suspends, the dict will contain __interrupt__ field with trigger data.
    When execution completes, the dict will contain final_result.
    """
    from langgraph.checkpoint.memory import MemorySaver

    # IMPORTANT: Must use checkpointer for interrupt() to work
    checkpointer = MemorySaver()
    graph = builder.compile(checkpointer=checkpointer)

    # Generate unique thread ID for this execution
    import uuid

    thread_id = f"agent-{uuid.uuid4()}"

    config = {"configurable": {"thread_id": thread_id}}

    result = graph.invoke(
        {"query": input_data.query, "process_result": None, "final_result": ""}, config
    )

    # Return raw dict - preserves __interrupt__ field if suspended
    # Runtime will detect __interrupt__ and create UiPath trigger
    return result
