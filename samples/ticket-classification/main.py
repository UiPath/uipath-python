import logging
import os
from typing import Literal, Optional, List

from langchain_openai import AzureChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import START, END, StateGraph
from langgraph.types import interrupt, Command
from pydantic import BaseModel, Field

from uipath_sdk import UiPathSDK
from uipath_sdk._models import CreateAction
logger = logging.getLogger(__name__)

uipath = UiPathSDK()

class GraphInput(BaseModel):
    message: str
    ticket_id: str
    assignee: Optional[str]

class GraphOutput(BaseModel):
    label: str
    confidence: float

class GraphState(BaseModel):
    message: str
    ticket_id: str
    assignee: Optional[str] = None
    label: Optional[str] = None
    confidence: Optional[float] = None
    predicted_categories: List[str] = []
    human_approval: Optional[bool] = None

class TicketClassification(BaseModel):
    label: Literal["security", "error", "system", "billing", "performance"] = Field(
        description="The classification label for the support ticket"
    )
    confidence: float = Field(
        description="Confidence score for the classification", ge=0.0, le=1.0
    )


output_parser = PydanticOutputParser(pydantic_object=TicketClassification)

prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """You are a support ticket classifier. Classify tickets into exactly one category and provide a confidence score.

{format_instructions}

Categories:
- security: Security issues, access problems, auth failures
- error: Runtime errors, exceptions, unexpected behavior
- system: Core infrastructure or system-level problems
- billing: Payment and subscription related issues
- performance: Speed and resource usage concerns

Respond with the classification in the requested JSON format.""",
        ),
        ("user", "{ticket_text}"),
    ]
)


def get_azure_openai_api_key() -> str:
    """Get Azure OpenAI API key from environment or UiPath."""
    api_key = os.getenv("AZURE_OPENAI_API_KEY")

    if not api_key:
        try:
            api_key = uipath.assets.retrieve_credential("AZURE_OPENAI_API_KEY")
            if not api_key:
                raise ValueError("No API key found in credentials")
        except Exception as e:
            logger.error(f"Failed to get API key: {str(e)}")
            raise RuntimeError("Failed to get Azure OpenAI API key")

    return api_key

def decide_next_node(state: GraphState) -> Literal["classify", "notify_team"]:
    if state.human_approval is True:
        return "notify_team"
    return "classify"

async def classify(state: GraphState) -> GraphState:
    """Classify the support ticket using LLM."""
    llm = AzureChatOpenAI(
        azure_deployment="gpt-4o-mini",
        api_key=get_azure_openai_api_key(),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version="2024-10-21"
    )
    new_state = GraphState(
        message=state.message,
        ticket_id=state.ticket_id,
        assignee=state.assignee,
        predicted_categories=state.predicted_categories.copy(),
        human_approval=state.human_approval
    )

    if len(new_state.predicted_categories) > 0:
        prompt.append(("user", f"The ticket is 100% not part of the following categories '{new_state.predicted_categories}'. Choose another one."))

    _prompt = prompt.partial(
        format_instructions=output_parser.get_format_instructions()
    )
    chain = _prompt | llm | output_parser

    try:
        result = await chain.ainvoke({"ticket_text": new_state.message})
        new_state.label = result.label
        new_state.predicted_categories.append(result.label)
        new_state.confidence = result.confidence
        logger.info(
            f"Ticket classified with label: {result.label} confidence score: {result.confidence}"
        )
        return new_state
    except Exception as e:
        logger.error(f"Classification failed: {str(e)}")
        return GraphState(
            message=new_state.message,
            ticket_id=new_state.ticket_id,
            assignee=new_state.assignee,
            predicted_categories=new_state.predicted_categories,
            human_approval=new_state.human_approval,
            label="error",
            confidence=0.0
        )

async def wait_for_human(state: GraphState) -> GraphState:
    logger.info("Wait for human approval")
    action_data = interrupt(CreateAction(name="escalation_agent_app",
                                         title="Action Required: Review classification",
                                         data={
                                             "AgentOutput": f"This is how I classified the ticket: '{state.ticket_id}', with message '{state.message}' \n Label: '{state.label}' Confidence: '{state.confidence}'",
                                             "AgentName": "ticket-classification "},
                                         app_version=1,
                                         assignee=state.assignee,
                                         ))
    new_state = GraphState(
        message=state.message,
        ticket_id=state.ticket_id,
        assignee=state.assignee,
        predicted_categories=state.predicted_categories.copy(),
        human_approval=isinstance(action_data["Answer"], bool) and action_data["Answer"] is True
    )
    return new_state

async def notify_team(state: GraphState) -> GraphOutput:
    logger.info("Send team email notification")
    return GraphOutput(label=state.label, confidence=state.confidence)

"""Process a support ticket through the workflow."""

builder = StateGraph(GraphState, input=GraphInput, output=GraphOutput)

builder.add_node("classify", classify)
builder.add_node("human_approval_node", wait_for_human)
builder.add_node("notify_team", notify_team)

builder.add_edge(START, "classify")
builder.add_edge("classify", "human_approval_node")
builder.add_conditional_edges("human_approval_node", decide_next_node)
builder.add_edge("notify_team", END)


from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()

graph = builder.compile(checkpointer=memory)
