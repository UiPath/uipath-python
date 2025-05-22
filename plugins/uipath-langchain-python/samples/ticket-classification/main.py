import logging
import os
from typing import Literal, Optional, List

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langgraph.graph import START, END, StateGraph, MessagesState
from langgraph.types import interrupt, Command
from pydantic import BaseModel, Field

from uipath import UiPath

from uipath.models import CreateAction
logger = logging.getLogger(__name__)

uipath = UiPath()

class GraphInput(BaseModel):
    message: str
    ticket_id: str
    assignee: Optional[str] = None

class GraphOutput(BaseModel):
    label: str
    confidence: float

class GraphState(MessagesState):
    message: str
    ticket_id: str
    assignee: Optional[str]
    label: Optional[str] = None
    confidence: Optional[float] = None
    last_predicted_category: Optional[str]
    human_approval: Optional[bool] = None

class TicketClassification(BaseModel):
    label: Literal["security", "error", "system", "billing", "performance"] = Field(
        description="The classification label for the support ticket"
    )
    confidence: float = Field(
        description="Confidence score for the classification", ge=0.0, le=1.0
    )


output_parser = PydanticOutputParser(pydantic_object=TicketClassification)
system_message = """You are a support ticket classifier. Classify tickets into exactly one category and provide a confidence score.

{format_instructions}

Categories:
- security: Security issues, access problems, auth failures
- error: Runtime errors, exceptions, unexpected behavior
- system: Core infrastructure or system-level problems
- billing: Payment and subscription related issues
- performance: Speed and resource usage concerns

Respond with the classification in the requested JSON format."""

def prepare_input(graph_input: GraphInput) -> GraphState:
    return GraphState(
        message=graph_input.message,
        ticket_id=graph_input.ticket_id,
        assignee=graph_input.assignee,
        messages=[
            SystemMessage(content=system_message.format(format_instructions=output_parser.get_format_instructions())),
            HumanMessage(content=graph_input.message)  # Add the initial human message
        ],
        last_predicted_category=None,
        human_approval=None,
    )

def decide_next_node(state: GraphState) -> Literal["classify", "notify_team"]:
    if state["human_approval"] is True:
        return "notify_team"

    return "classify"

async def classify(state: GraphState) -> Command:
    """Classify the support ticket using LLM."""
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    if state.get("last_predicted_category", None):
        predicted_category = state["last_predicted_category"]
        state["messages"].append(HumanMessage(content=f"The ticket is 100% not part of the category '{predicted_category}'. Choose another one."))
    chain = llm | output_parser

    try:
        result = await chain.ainvoke(state["messages"])
        logger.info(
            f"Ticket classified with label: {result.label} confidence score: {result.confidence}"
        )
        return Command(
           update={
               "confidence": result.confidence,
               "label": result.label,
               "last_predicted_category": result.label,
               "messages": state["messages"],
           }
        )
    except Exception as e:
        logger.error(f"Classification failed: {str(e)}")
        return Command(
            update={
                "label": "error",
                "confidence": "0.0",
            }
        )

async def wait_for_human(state: GraphState) -> Command:
    logger.info("Wait for human approval")
    ticket_id = state["ticket_id"]
    ticket_message = state["messages"][1].content
    label = state["label"]
    confidence = state["confidence"]
    action_data = interrupt(CreateAction(app_name="escalation_agent_app",
                                         title="Action Required: Review classification",
                                         data={
                                             "AgentOutput": (
                                                 f"This is how I classified the ticket: '{ticket_id}',"
                                                 f" with message '{ticket_message}' \n"
                                                 f"Label: '{label}'"
                                                 f" Confidence: '{confidence}'"
                                             ),
                                             "AgentName": "ticket-classification "},
                                         app_version=1,
                                         assignee=state.get("assignee", None),
                                         app_folder_path="Shared/escalation_app",
                                         ))

    return Command(
        update={
            "human_approval": isinstance(action_data["Answer"], bool) and action_data["Answer"] is True
    }
    )

async def notify_team(state: GraphState) -> GraphOutput:
    logger.info("Send team email notification")
    return GraphOutput(label=state["label"], confidence=state["confidence"])

"""Process a support ticket through the workflow."""

builder = StateGraph(GraphState, input=GraphInput, output=GraphOutput)

builder.add_node("prepare_input", prepare_input)
builder.add_node("classify", classify)
builder.add_node("human_approval_node", wait_for_human)
builder.add_node("notify_team", notify_team)

builder.add_edge(START, "prepare_input")
builder.add_edge("prepare_input", "classify")
builder.add_edge("classify", "human_approval_node")
builder.add_conditional_edges("human_approval_node", decide_next_node)
builder.add_edge("notify_team", END)


from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()

graph = builder.compile(checkpointer=memory)
