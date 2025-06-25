# type: ignore
import dataclasses
import time
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel
from uipath.models import InvokeProcess, Job, WaitJob


@dataclasses.dataclass
class Input:
    pass


class GraphState(BaseModel):
    process_output: Optional[str] = None


@dataclasses.dataclass
class Output:
    message: str


def create_process_node(input: Input) -> Command:
    response = interrupt(
        InvokeProcess(
            name="PROCESS NAME",
            process_folder_path="process-folder-path",
            input_arguments={"input_arg_1": "value_1"},
        )
    )

    # sleep 1 sec to increase the new trigger timestamp
    time.sleep(1)
    return Command(update={"process_output": response["output_arg_1"]})


def wait_job_node(state: GraphState) -> Output:
    print("Process output: {}".format(state.process_output))

    response = interrupt(
        WaitJob(job=Job(key="487d9dc7-30fe-4926-b5f0-35a956914042", Id=123))
    )
    return Output(message=response["output_arg_2"])


builder = StateGraph(GraphState, input=Input, output=Output)

builder.add_node("create_process_node", create_process_node)
builder.add_node("wait_job_node", wait_job_node)

builder.add_edge(START, "create_process_node")
builder.add_edge("create_process_node", "wait_job_node")
builder.add_edge("wait_job_node", END)


memory = MemorySaver()

graph = builder.compile(checkpointer=memory)
