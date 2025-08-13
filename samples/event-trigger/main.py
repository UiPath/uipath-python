from dataclasses import dataclass
from uipath.models import EventArguments
from uipath import UiPath
from uipath.tracing import traced
import logging

logger = logging.getLogger(__name__)

@dataclass
class EchoOut:
    message: dict

@traced()
def handle_slack_event(payload: dict[str, any]) -> EchoOut:
    """Handle Slack message events"""
    message = payload['event']['text'] if 'event' in payload and 'text' in payload['event'] else "No message"
    user = payload['event']['user'] if 'event' in payload and 'user' in payload['event'] else "Unknown user"

    logger.info(f"Slack message from {user}: {message}")


# use InputTriggerEventArgs when called by UiPath EventTriggers
@traced()
def main(input: EventArguments) -> EchoOut:
    sdk = UiPath()

    # get the event payload, this will be different from event to event
    payload = sdk.connections.retrieve_event_payload(input)

    handle_slack_event(payload)

    logger.info(f"Received payload: {payload}")

    return EchoOut(payload)
