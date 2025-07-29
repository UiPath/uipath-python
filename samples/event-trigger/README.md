# UiPath Coded Agents with Event Triggers

This guide explains how to create Python-based UiPath Coded Agents that respond to event triggers, enabling seamless event-driven agents.

## Overview

UiPath Coded Agents allow you to write automation logic directly in Python while leveraging UiPath's event trigger system. This project demonstrates how to create agents that handle external events from systems like Gmail, Slack, and other connectors.

## How to Set Up UiPath Coded Agents with Event Triggers

### Step 1: Install UiPath Python SDK

1. Open it with your prefered editor
2. In terminal run:
```bash
uv init
uv add uipath
uv run uipath new event-agent
uv run uipath init
```

### Step 2: Create Your Coded Agent

Create a Python file with your agent logic using the UiPath SDK:

```python
from dataclasses import dataclass
from uipath.models import EventArguments
from uipath import UiPath
import logging

logger = logging.getLogger(__name__)

@dataclass
class EchoOut:
    message: dict

# use EventArguments when called by UiPath EventTriggers
def main(input: EventArguments) -> EchoOut:
    sdk = UiPath()

    # get the event payload, this will be different from event to event
    payload = sdk.connections.retrieve_event_payload(input)

    logger.info(f"Received payload: {payload}")

    return EchoOut(payload)
```

Run `uipath init` again to update the input arguments.

### Step 3: Understanding the Event Flow

When an event trigger fires, UiPath will:
1. Pass event data through `EventArguments`
2. Your agent retrieves the full payload using `sdk.connections.retrieve_event_payload(input)`
3. Process the payload based on your business logic
4. Return structured output

### Step 4: Publish Your Coded Agent and setup Event Trigger

#### 4.1: Build and Publish
1. Use `uipath pack` and `uipath publish` to create and publish the package
2. Create an Orchestrator Automation from the published process

#### 4.2: Access Event Triggers
1. Log into UiPath Orchestrator
2. Navigate to **Automations** → **Processes**
3. Click on your coded workflow process

#### 4.3: Create Event Trigger
1. Go to the **Triggers** tab
2. Click **Add Trigger** → **Event Trigger**

#### 4.4: Configure Event Trigger Settings
1. **Name**: Descriptive name (e.g., "Gmail Event Handler")
2. **Event Source**: Select connector type:
   - `uipath-google-gmailcustom` for Gmail
   - `uipath-slack` for Slack
   - `uipath-microsoft-outlookcustom` for Outlook
   - Custom connectors
3. **Event Type**: Choose specific event:
   - `EMAIL_RECEIVED` for emails
   - `MESSAGE_RECEIVED` for chat messages
   - Custom event types
4. **Filters**: Optional event filtering criteria

#### 4.5: Map Event to Input Arguments
The event data will automatically be passed to your `EventArguments` parameter.

#### 4.6: Enable the Trigger
1. Review configuration
2. Click **Create** to save
3. Ensure trigger status is **Enabled**

### Step 5: Test Your Setup

#### 5.1: Trigger Test Events
- Send test email (Gmail triggers)
- Post message in Slack (Slack triggers)
- Perform action matching your event source

#### 5.2: Monitor Execution
1. Check **Monitoring** → **Jobs** in Orchestrator
2. View job details and execution logs
3. Verify your coded agent processed the event correctly

#### 5.3: Debug with Logs

```python
import logging

logger = logging.getLogger(__name__)

def main(input: EventArguments) -> EchoOut:
    sdk = UiPath()
    
    # payload will be a json (dict) specific to your event
    payload = sdk.connections.retrieve_event_payload(input)
    logger.info(f"Successfully retrieved payload: {type(payload)}")
    logger.debug(f"Payload details: {payload}")
    
    # Your processing logic here
    result = process_event(payload)
    
    logger.info(f"Event processed successfully: {result}")
    return EchoOut(result)
```