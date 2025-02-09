import os 
import sys
import logging
import traceback
from typing import Dict, Any
from enum import Enum
from dotenv import load_dotenv
from uipath_sdk import UiPathSDK
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import MessageGraph
from langgraph.checkpoint import SQLiteCheckpoint
from langchain_core.output_parsers import EnumOutputParser
from langgraph.pregel import InterruptException

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
load_dotenv()

secret = os.environ.get("UIPATH_TOKEN")
uipath = UiPathSDK(secret)

class TicketLabel(str, Enum):
    SECURITY = "security"          # Security vulnerabilities, access issues, authentication
    ERROR = "error"                # Runtime errors, exceptions, crashes
    SYSTEM = "system"              # Core system issues, deployment, infrastructure
    BILLING = "billing"            # Payment processing, subscriptions, invoices
    PERFORMANCE = "performance"    # Slow response times, resource usage, optimization

prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a support ticket classifier. Classify tickets into exactly one category:
    - security: Security issues, access problems, auth failures
    - error: Runtime errors, exceptions, unexpected behavior
    - system: Core infrastructure or system-level problems
    - billing: Payment and subscription related issues
    - performance: Speed and resource usage concerns
    
    Respond with just the category name, no explanation."""),
    ("user", "{ticket_text}")
])

output_parser = EnumOutputParser(enum_cls=TicketLabel)

def get_anthropic_api_key() -> str:
    """Get Anthropic API key from environment or UiPath."""
    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        try:
            api_key = uipath.robot_assets.retrieve("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("No API key found in credentials")
        except Exception as e:
            logger.error(f"Failed to get API key: {str(e)}")
            raise RuntimeError("Failed to get Anthropic API key")
        
    return api_key

async def classify(state: Dict[str, Any]) -> Dict[str, Any]:
    """Classify the support ticket using LLM."""
    llm = ChatAnthropic(
        api_key=get_anthropic_api_key(),
        model="claude-3-sonnet-20240229"
    )

    chain = prompt | llm | output_parser
    try:
        label = await chain.ainvoke({"ticket_text": state["message"]})
        state["label"] = label
    except Exception as e:
        # Fallback to ERROR category if classification fails
        logger.error(f"Classification failed: {str(e)}")
        state["label"] = TicketLabel.ERROR

    return state

async def wait_for_human(state: Dict[str, Any]) -> Dict[str, Any]:
    """Placeholder for human approval request."""
    raise InterruptException()

def process(ticket_data: Dict[str, Any]) -> Any:
    """Process a support ticket through the workflow."""
    checkpoint = SQLiteCheckpoint("uipath.db", "support_tickets")
    graph = MessageGraph()
    
    graph.add_node("classify", classify)
    graph.add_node("human_approval", wait_for_human)
    
    graph.add_edge("classify", "human_approval")
    graph.set_entry_point("classify")
    
    workflow = graph.compile(checkpointer=checkpoint)
    
    return workflow.invoke(ticket_data)

def main() -> None:
    """Main entry point for the ticket classification system."""
    ticket = {
        "message": "Having error connecting to database",
        "ticket_id": "TICKET-123"
    }
       
    try:
        process(ticket)
        sys.exit(0)
    except InterruptException:
        sys.exit(100)
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
        
if __name__ == "__main__":
    main()