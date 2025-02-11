# Support Ticket Classification System

Use LangGraph with Anthropic to automatically classify support tickets into predefined categories with confidence scores. UiPath integration with Action Center for human approval step.

## Debug

1. Clone the repository:
```bash
git clone 
cd ticket-classification
```

2. Install dependencies:

3. Create a `.env` file in the project root with the following configuration:
```env
UIPATH_ACCESS_TOKEN=your_access_token
UIPATH_URL=https://alpha.uipath.com/ada/byoa
UIPATH_FOLDER_PATH=Pufos
UIPATH_ROBOT_KEY=805d2237-34e3-41f3-bfc3-710f808926b2
UIPATH_JOB_KEY=805d2237-34e3-41f3-bfc3-710f808926b5
ANTHROPIC_API_KEY=your_anthropic_api_key
```

### Basic Classification

To classify a ticket, run the script with a JSON ticket object:

```bash
python main.py '{"message": "GET Assets API does not enforce proper permissions Assets.View", "ticket_id": "TICKET-2345"}'
```

### Resume with Approval

To resume a suspended job with approval:

```bash
python main.py '{"message": "GET Assets API does not enforce proper permissions Assets.View", "ticket_id": "TICKET-2345"}' true
```

### Input JSON Format

The input ticket should be in the following format:
```json
{
    "message": "The ticket message or description",
    "ticket_id": "Unique ticket identifier"
}
```

### Output Format

The script outputs JSON with the classification results:
```json
{
    "message": "Original ticket message",
    "ticket_id": "TICKET-ID",
    "label": "security",
    "confidence": 0.9,
    "approved": true
}
```