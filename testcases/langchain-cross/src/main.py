from langgraph.graph import START, StateGraph, END
from pydantic import BaseModel
import os

class GraphState(BaseModel):
    topic: str

class GraphOutput(BaseModel):
    report: str

async def generate_report(state: GraphState) -> GraphOutput:
    report = "Just a sanity report"
    return GraphOutput(report=report)

builder = StateGraph(GraphState, output=GraphOutput)

builder.add_node("generate_report", generate_report)

builder.add_edge(START, "generate_report")
builder.add_edge("generate_report", END)

graph = builder.compile()
