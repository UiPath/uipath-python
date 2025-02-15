import sys
import logging
import traceback
import json
from dotenv import load_dotenv
from typing import Annotated, Any, Dict, Optional
from uipath_sdk import UiPathSDK
from uipath_sdk.package._arguments import InputArgument, OutputArgument

logger = logging.getLogger(__name__)
load_dotenv()

uipath = UiPathSDK()

class JiraTicket:
    message: Annotated[str, InputArgument(), OutputArgument()]
    ticket_id: Annotated[str, InputArgument(), OutputArgument()]
    label: Annotated[Optional[str], OutputArgument()] = None
    confidence: Annotated[Optional[float], OutputArgument()] = None
    approved: Annotated[Optional[bool], OutputArgument()] = None

def main():
    try:
        ticket: Dict[str, Any] = json.loads(sys.argv[1])
        print(json.dumps(ticket, indent=2))
        sys.exit(0)
    except Exception as e:
        logger.error(f"Error occurred: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)
        
if __name__ == "__main__":
    main()