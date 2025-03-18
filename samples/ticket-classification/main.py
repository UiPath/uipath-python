import logging
import os
from typing import Literal, Optional

from langchain_openai import AzureChatOpenAI
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import START, END, StateGraph
from langgraph.types import interrupt, Command
from pydantic import BaseModel, Field

from uipath_sdk import UiPathSDK

logger = logging.getLogger(__name__)

uipath = UiPathSDK()

class GraphInput(BaseModel):
    message: str
    ticket_id: str

class GraphOutput(BaseModel):
    label: str
    confidence: float

class GraphState(BaseModel):
    message: str
    ticket_id: str
    label: Optional[str] = None
    confidence: Optional[float] = None


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


async def classify(state: GraphState) -> GraphState:
    """Classify the support ticket using LLM."""
    llm = AzureChatOpenAI(
        azure_deployment="gpt-4o-mini",
        api_key=get_azure_openai_api_key(),
        azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        api_version="2024-10-21"
    )
    _prompt = prompt.partial(
        format_instructions=output_parser.get_format_instructions()
    )
    chain = _prompt | llm | output_parser

    try:
        result = await chain.ainvoke({"ticket_text": state.message})
        print(result)
        state.label = result.label
        state.confidence = result.confidence
        logger.info(
            f"Ticket classified with label: {result.label} confidence score: {result.confidence}"
        )
        return state
    except Exception as e:
        logger.error(f"Classification failed: {str(e)}")
        state.label = "error"
        state.confidence = 0.0
        return state

async def wait_for_human(state: GraphState) -> GraphState:
    logger.info("Wait for human approval")
    feedback = interrupt(f"Label: {state.label} Confidence: {state.confidence}")

    if isinstance(feedback, bool) and feedback is True:
        return Command(goto="notify_team")
    else:
        return Command(goto=END)

async def notify_team(state: GraphState) -> GraphState:
    logger.info("Send team email notification")
    print(state)
    return state

"""Process a support ticket through the workflow."""

builder = StateGraph(GraphState, input=GraphInput, output=GraphOutput)

builder.add_node("classify", classify)
builder.add_node("human_approval", wait_for_human)
builder.add_node("notify_team", notify_team)

builder.add_edge(START, "classify")
builder.add_edge("classify", "human_approval")
builder.add_edge("human_approval", "notify_team")
builder.add_edge("notify_team", END)


from langgraph.checkpoint.memory import MemorySaver

memory = MemorySaver()

graph = builder.compile(checkpointer=memory)
