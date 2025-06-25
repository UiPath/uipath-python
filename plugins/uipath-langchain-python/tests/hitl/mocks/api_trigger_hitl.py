import dataclasses

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


@dataclasses.dataclass
class Input:
    pass


@dataclasses.dataclass
class Output:
    message: str


def main_node(input: Input) -> Output:
    response = interrupt("interrupt message")
    return Output(message=response)


builder = StateGraph(input=Input, output=Output)

builder.add_node("main_node", main_node)

builder.add_edge(START, "main_node")
builder.add_edge("main_node", END)


memory = MemorySaver()

graph = builder.compile(checkpointer=memory)
