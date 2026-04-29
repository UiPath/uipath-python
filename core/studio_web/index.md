# Studio Web Integration

[Studio Web](https://docs.uipath.com/studio-web/automation-cloud/latest/user-guide/overview) is a cloud IDE for building projects such as RPAs, low code agents, and API workflows. It also supports importing coded agents built locally. Bringing your coded agent into Studio Web gives you:

- Cloud debugging with dynamic breakpoints
- Running and defining evaluations directly in the cloud
- A unified build experience alongside multiple project types
- Self contained solution deployment units

There are two ways to connect a coded agent to Studio Web: using a [Cloud Workspace](#cloud-workspace) or a [Local Workspace](#local-workspace).

______________________________________________________________________

## Cloud Workspace

In a Cloud Workspace, your project lives in Studio Web and you sync code between your local IDE and the cloud.

### Importing a Coded Agent

1. Open your solution in Studio Web
1. Create a new Agent and select **Coded**
1. Choose a sample project to start from, or push an existing local agent

### Pushing an Existing Agent

If you already have a coded agent locally, you can sync it to Studio Web:

1. Copy the `UIPATH_PROJECT_ID` from Studio Web into your `.env` file

1. Push your project:

   uipath pushPushing UiPath project to Studio Web...\
   Uploading 'main.py'\
   Uploading 'uipath.json'\
   Updating 'pyproject.toml'\
   Uploading '.uipath/studio_metadata.json'\
   Importing referenced resources to Studio Web project...\
   🔵 Resource import summary: 3 total resources - 1 created, 1 updated, 1 unchanged, 0 not found

   Notice the **Resource import summary** at the end. The push command also imports resources defined in `bindings.json` into the Studio Web solution, just like importing resources for a low code agent. This ensures that all required resources are packaged with the solution, so the coded agent works anywhere the solution is deployed.

   See [`uipath push`](https://uipath.github.io/uipath-python/cli/index.md) in the CLI Reference.

### Pulling Changes

To pull the latest version from Studio Web to your local environment:

uipath pullPulling UiPath project from Studio Web...\
Processing: main.py\
File 'main.py' is up to date\
Processing: uipath.json\
File 'uipath.json' is up to date\
Processing: bindings.json\
File 'bindings.json' is up to date\
Processing: evaluations\\eval-sets\\evaluation-set-default.json\
Downloaded 'evaluations\\eval-sets\\evaluation-set-default.json'\
Processing: evaluations\\evaluators\\evaluator-default.json\
Downloaded 'evaluations\\evaluators\\evaluator-default.json'\
✓ Project pulled successfully

See [`uipath pull`](https://uipath.github.io/uipath-python/cli/index.md) in the CLI Reference.

______________________________________________________________________

## Local Workspace

Preview Feature

The local workspace integration is currently experimental. Behavior is subject to change in future versions.

In a Local Workspace, your project lives on your machine and is linked to a Studio Web solution. See the [Local Workspace documentation](https://docs.uipath.com/studio-web/automation-cloud/latest/user-guide/solutions-in-the-local-workspace) for setup details.

You can either start from a predefined template in Studio Web or set up a new agent from scratch.

### Starting from a Template

When creating a new Coded agent in Studio Web with a Local Workspace, you can pick one of the predefined templates. This creates the project files directly on your machine. Templates come with sample code and predefined evaluations you can run immediately.

### Setting Up a New Agent

You can also create a coded agent from scratch in your local IDE and have it appear in Studio Web.

First, install the SDK package for the framework you want to use:

# Pick the package that matches your framework:# uipath-langchain - LangChain / LangGraph# uipath-openai-agents - OpenAI Agents SDK# uipath-llamaindex - LlamaIndex# uipath-pydantic-ai - PydanticAI# uipath-google-adk - Google ADK# uipath-agent-framework - UiPath Agent Frameworkuv add uipath-langchainResolved 42 packages in 1.2s

Installed 42 packages in 0.8s

# Pick the package that matches your framework:# uipath-langchain - LangChain / LangGraph# uipath-openai-agents - OpenAI Agents SDK# uipath-llamaindex - LlamaIndex# uipath-pydantic-ai - PydanticAI# uipath-google-adk - Google ADK# uipath-agent-framework - UiPath Agent Frameworkpip install uipath-langchainSuccessfully installed uipath-langchain

Then authenticate, scaffold the agent, and initialize the project:

uipath auth⠋ Authenticating with UiPath ...\
🔗 If a browser window did not open, please open the following URL in your browser: [LINK]\
👇 Select tenant:\
0: Tenant1\
1: Tenant2\
Select tenant number: 0\
Selected tenant: Tenant1\
✓ Authentication successful.\
uipath new agent✓ Created new agent project.\
uipath init⠋ Initializing UiPath project ...\
✓ Created 'entry-points.json' file.

That's it, your agent should now be visible in Studio Web.

______________________________________________________________________

## Publishing

Once your coded agent is in Studio Web, publishing works the same as any other project. Click **Publish** in Studio Web and it will be packaged and deployed through the standard workflow.

______________________________________________________________________

## Running and Debugging

Your agent can be run both in the cloud (via Studio Web) and locally using the CLI.

### Running Locally

uipath run agent '{"message": "hello"}'

See [`uipath run`](https://uipath.github.io/uipath-python/cli/index.md) in the CLI Reference.

### Debugging Locally

Use `uipath debug` for an enhanced local debugging experience. Unlike `uipath run`, the debug command:

- Auto polls for trigger responses when the agent suspends (e.g., LangGraph interrupts)
- Fetches binding overwrites from Studio Web (configurable in **Debug > Debug Configuration > Solution resources**)

uipath debug agent '{"message": "hello"}'

See [`uipath debug`](https://uipath.github.io/uipath-python/cli/index.md) in the CLI Reference.

### Evaluating Locally

Run evaluations against your agent using the CLI:

uipath eval agent .\\evaluations\\eval-sets\\faithfulness-multi-model.json

See [`uipath eval`](https://uipath.github.io/uipath-python/cli/index.md) in the CLI Reference and the [Evaluations documentation](https://uipath.github.io/uipath-python/eval/index.md).

______________________________________________________________________

## Syncing Evaluations

Evaluations can be defined either in Studio Web or locally. They sync automatically when you use `uipath pull` and `uipath push`.

Note

Custom evaluators must be created locally. See [Custom Evaluators](https://uipath.github.io/uipath-python/eval/custom_evaluators/index.md) for details.
