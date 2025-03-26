# Support Ticket Classification System

Use LangGraph with Azure OpenAI to automatically classify support tickets into predefined categories with confidence scores. UiPath Orchestrator API integration for human approval step.

## Debug

1. Clone the repository:
```bash
git clone
cd samples\ticket-classification
```

2. Install dependencies:
```bash
pip install uv
uv venv -p 3.11 .venv
.venv\Scripts\activate
uv sync
```

3. Create a `.env` file in the project root with the following configuration:
```env
UIPATH_URL=https://alpha.uipath.com/ada/byoa
UIPATH_ACCESS_TOKEN=xxx
AZURE_OPENAI_API_KEY=xxx
AZURE_OPENAI_ENDPOINT=xxx
```

```bash
uipath run <entrypoint> <input> [--resume]
```

### Run

To classify a ticket, run the script using UiPath CLI:

```bash
uipath run agent '{"message": "GET Assets API does not enforce proper permissions Assets.View", "ticket_id": "TICKET-2345"}'
```

### Resume

To resume the graph with approval:

```bash
uipath run agent true --resume
```

### Input Format

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
    "label": "security",
    "confidence": 0.9
}
```
