import os 
import sys
import asyncio
import logging
import traceback
import json
from typing import Dict, Any, Literal, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from uipath_sdk import UiPathSDK
from langgraph.types import interrupt
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph
from langgraph.graph.state import Command
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langchain_core.output_parsers import PydanticOutputParser

logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

uipath = UiPathSDK()

class GraphState(BaseModel):
    message: str
    ticket_id: str
    label: Optional[str] = None
    confidence: Optional[float] = None
    approved: Optional[bool] = None

class TicketClassification(BaseModel):
    label: Literal["security", "error", "system", "billing", "performance"] = Field(
        description="The classification label for the support ticket"
    )
    confidence: float = Field(
        description="Confidence score for the classification",
        ge=0.0,
        le=1.0
    )

output_parser = PydanticOutputParser(pydantic_object=TicketClassification)

prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a support ticket classifier. Classify tickets into exactly one category and provide a confidence score.

{format_instructions}

Categories:
- security: Security issues, access problems, auth failures
- error: Runtime errors, exceptions, unexpected behavior
- system: Core infrastructure or system-level problems
- billing: Payment and subscription related issues
- performance: Speed and resource usage concerns

Respond with the classification in the requested JSON format."""),
    ("user", "{ticket_text}")
])

def get_anthropic_api_key() -> str:
    """Get Anthropic API key from environment or UiPath."""
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        try:
            api_key = uipath.assets.retrieve("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("No API key found in credentials")
        except Exception as e:
            logger.error(f"Failed to get API key: {str(e)}")
            raise RuntimeError("Failed to get Anthropic API key")
        
    return api_key

async def classify(state: GraphState) -> GraphState:
    """Classify the support ticket using LLM."""
    llm = ChatAnthropic(
        api_key=get_anthropic_api_key(),
        model="claude-3-opus-20240229"
    )

    _prompt = prompt.partial(format_instructions=output_parser.get_format_instructions())
    chain = _prompt | llm | output_parser

    try:
        result = await chain.ainvoke({"ticket_text": state.message})
        state.label = result.label
        state.confidence = result.confidence
        logger.info(f"Ticket classified with label: {result.label} confidence score: {result.confidence}")
        return state
    except Exception as e:
        logger.error(f"Classification failed: {str(e)}")
        state.label = "error"
        state.confidence = 0.0
        return state

class InterruptDetected(Exception):
    """Custom exception to indicate an interrupt was triggered."""
    pass

async def wait_for_human(state: GraphState) -> GraphState:
    logger.info("Processing ticket...")
    
    if state.approved is None:
        logger.info("Needs human approval")
        raise InterruptDetected()
    
#    if state.approved is None:
#        logger.info("Needs human approval")
#        state.approved = interrupt("Waiting for human approval")
    
    if state.approved:
        logger.info("Ticket approved - continuing")
        return state

async def process(ticket_data: Dict[str, Any]) -> Any:
    """Process a support ticket through the workflow."""
    builder = StateGraph(GraphState)
    
    builder.add_node("classify", classify)
    builder.add_node("human_approval", wait_for_human)
    
    builder.add_edge("classify", "human_approval")
    builder.set_entry_point("classify")

    async with AsyncSqliteSaver.from_conn_string("uipath.db") as memory:
        graph = builder.compile(checkpointer=memory)
    
        config = {
            "configurable": {
                "thread_id": uipath._execution_context.instance_id
            }
        }
        state = GraphState(**ticket_data)

#        if state.approved:
#            return await graph.ainvoke(Command(resume=state), config)
        
        return await graph.ainvoke(state, config)

async def main() -> None:
    """Main entry point for the ticket classification system."""

    if len(sys.argv) < 2:
        logger.error("Please provide a ticket JSON as the first argument")
        sys.exit(1)

    ticket: Dict[str, Any] = json.loads(sys.argv[1])

    approved = len(sys.argv) > 2 and sys.argv[2].lower() == 'true'
    ticket['approved'] = approved if len(sys.argv) > 2 else None
       
    try:
        result = await process(ticket)
        print(json.dumps(result))
        logger.info("Successful exit")
        sys.exit(0)
    except InterruptDetected:
        logger.info("Job suspended")
        sys.exit(100)
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
        
if __name__ == "__main__":
    asyncio.run(main())