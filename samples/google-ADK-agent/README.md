# UiPath Google ADK Agent

## Overview

This project showcases how to run Google's Agent Development Kit (ADK) agents on the UiPath Platform using the UiPath SDK. The implementation follows the [Google ADK Quickstart](https://google.github.io/adk-docs/get-started/quickstart/#agentpy) guide, demonstrating the ability to deploy and execute ADK agents within the UiPath ecosystem.

## Features

- Integration with Google's Gemini model
- Seamless deployment to UiPath Platform

## Prerequisites

1. Python 3.10+
2. Google AI Studio API key
3. UiPath Platform account

## Setup and Configuration

1. **Create and activate a virtual environment**:
   ```bash
   pip install uv
   uv venv
   # Windows
   .venv\Scripts\activate
   # Unix/MacOS
   source .venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   uv sync
   ```

3. **Initialize UiPath configuration**:
   ```bash
   uipath init .\multi_tool_agent\agent.py
   ```
   This command will create (or update):
   - `uipath.json`: Contains input/output schemas and bindings
   - `.env`: Template for environment variables

   For more details about the init command, see the [CLI Reference documentation](https://uipath.github.io/uipath-python/cli/#init).

4. **Configure environment variables**:
   Update the `.env` file with:
   ```
   GOOGLE_GENAI_USE_VERTEXAI=FALSE
   GOOGLE_API_KEY=YOUR_API_KEY_HERE
   ```

## Deployment to UiPath Platform

1. **Authenticate with UiPath**:
   ```bash
   uipath auth
   ```

2. **Package the agent**:
   ```bash
   uipath pack
   ```

3. **Publish to your workspace**:
   ```bash
   uipath publish --my-workspace
   ```

## Running the Agent

### On UiPath Platform

1. **Using CLI**:
   ```bash
   uipath invoke agent --file input.json
   ```

2. **From Orchestrator**:
   - Navigate to Processes
   - Find your published agent
   - Click Run
   - Provide input parameters

### Local Development

For local testing and development:
```bash
uipath run agent --file input.json
# Debug mode
uipath run agent --file input.json --debug
```

## Example Query and Output

Query:
```
"What time is it in New York, and what's the weather like?"
```

When running on the UiPath Platform, you'll see the output in the job details:

![Agent Output in UiPath Platform](../../docs/sample_images/google-ADK-agent/agent-output.png)

## Notes

- The agent uses Google's Gemini model for natural language processing
- All agent interactions are logged and can be monitored through UiPath's tracing capabilities
- The agent can be extended with additional tools and capabilities

For more information about Google ADK, visit the [official documentation](https://google.github.io/adk-docs/).
