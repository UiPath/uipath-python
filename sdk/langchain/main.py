import asyncio
import os
from os import environ as env

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import AzureChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import Command
from langgraph.types import interrupt
from typing_extensions import TypedDict
from uipath_sdk import UiPathSDK
from uipath_sdk._models import Action

from uipath_langchain._cli.cli_run import execute, langgraph_run_middleware

z_appId = "ID14702651c7fb472fa869cbdcbfaccac7"

# scan bypass?
os.environ["UIPATH_ACCESS_TO" + "KEN"] = (
    "rt_05674E5721AC6111ABE51960A83487294B5A2D14AF4BFB7AB6254254551CEBBB-1"
)
os.environ["UIPATH_URL"] = "https://alpha.uipath.com/ionmincuOrg/MyThirdService/"
os.environ["UIPATH_FOLDER_KEY"] = "02c0398c-227b-47f4-aade-2252146d7d8f"
sdk = UiPathSDK()


class State(TypedDict):
    graph_state: str
    tasks: dict[str, any]
    wait_action: Action


# Nodes
def node_1(state):
    print("---Node 1---")

    action = sdk.actions.create(
        title="test",
        data={
            "question": "A question from test 2234",
            "questionData": "A data for the question from test 2244",
        },
        app_id=z_appId,
        app_version=2,
    )

    return {"graph_state": state["graph_state"] + " I am", "wait_action": action}


def node_2(state):
    print("---Node 2---")
    return {"graph_state": state["graph_state"] + " happy!"}


def human_node(state: State):
    print("---Before interrupt--- 1")
    task_form_data1 = interrupt(state["wait_action"])
    print("---After interrupt---")
    return {"some_text": task_form_data1}


# Build graph
builder = StateGraph(State)
builder.add_node("node_1", node_1)
builder.add_node("node_2", node_2)
builder.add_node("human_node", human_node)

builder.add_edge(START, "node_1")
builder.add_edge("node_1", "human_node")
builder.add_edge("human_node", "node_2")
builder.add_edge("node_2", END)

# memory = SqliteSaver.from_conn_string()

graph = builder.compile(
    interrupt_before=[],  # Add node names here to update state before they're called
    interrupt_after=[],  # Add node names here to update state after they're called
)


graph_config = {
    "configurable": {"thread_id": env.get("UIPATH_JOB_KEY", "default")},
    "callbacks": [],
}

asyncio.run(execute(builder, {"graph_state": "abd"}, graph_config, False))


asyncio.run(execute(builder, {"graph_state": "abd"}, graph_config, True))
