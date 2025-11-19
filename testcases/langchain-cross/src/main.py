from langgraph.graph import START, StateGraph, END
from langsmith import traceable
from uipath.tracing import traced
from pydantic import BaseModel
import logging
from opentelemetry import trace, baggage

tracer = trace.get_tracer("my.tracer")


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@traceable
def my_custom_traceable_function(input: str) -> str:
    logger.warning(f"Testing traceable: {input}")
    # Custom function to process the input
    return { "a": "HARD-CODED-OUTPUT-1" }

@traced()
def my_custom_nested_traced_function(input: str) -> str:
    logger.warning(f"Testing nested traced from uipath: {input}")
    # Custom function to process the input
    return { "a-nested": "HARD-CODED-OUTPUT-2" }


@traced()
def my_custom_traced_function(input: str) -> str:
    logger.warning(f"Testing traced from uipath: {input}")

    my_custom_nested_traced_function(input)
    # Custom function to process the input
    return { "a": "HARD-CODED-OUTPUT-2" }

@traced(name="factorial")
async def factorial(i: int=0) -> int:
    logger.info(f"Calculating factorial of {i}")
    if i <= 1:
        return 1
    return i * await factorial(i=i - 1)


class GraphState(BaseModel):
    topic: str

class GraphOutput(BaseModel):
    report: str

async def generate_report(state: GraphState) -> GraphOutput:

    # with tracer.start_as_current_span(name="manual_root") as root_span:
    #     with tracer.start_as_current_span(name="manual_child_span") as child_span:
    #         my_custom_traceable_function("test-1")
    #         my_custom_traced_function("test-2")
    #         await factorial(5)

    my_custom_traceable_function("test-1")
    my_custom_traced_function("test-2")
    await factorial(5)

    report = "Just a sanity report"
    return GraphOutput(report=report)

builder = StateGraph(GraphState, output=GraphOutput)

builder.add_node("generate_report", generate_report)

builder.add_edge(START, "generate_report")
builder.add_edge("generate_report", END)

graph = builder.compile()
