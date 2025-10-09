# Agent Code Patterns Reference

This document provides practical code patterns for building UiPath coded agents using LangGraph and the UiPath Python SDK.

---

## Core Agent Patterns

### Pattern 1: Simple Agent (Single LLM Call)

**Use Case**: Text transformation, summarization, analysis, classification
**Components**: Input → Single LLM node → Output

```python
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import START, StateGraph, END
from uipath_langchain.chat import UiPathChat
from pydantic import BaseModel

class Input(BaseModel):
    text: str

class State(BaseModel):
    text: str
    result: str = ""

class Output(BaseModel):
    result: str

llm = UiPathChat(model="gpt-4o-2024-08-06", temperature=0.7)

async def process(state: State) -> State:
    response = await llm.ainvoke([
        SystemMessage("You are a helpful assistant that summarizes text."),
        HumanMessage(state.text)
    ])
    return State(text=state.text, result=response.content)

async def create_output(state: State) -> Output:
    return Output(result=state.result)

builder = StateGraph(State, input=Input, output=Output)
builder.add_node("process", process)
builder.add_node("output", create_output)
builder.add_edge(START, "process")
builder.add_edge("process", "output")
builder.add_edge("output", END)

graph = builder.compile()
```

**Key Points**:
- Simplest pattern for text-to-text transformations
- Use `SystemMessage` for instructions, `HumanMessage` for content
- Always use async/await for LLM calls

---

### Pattern 2: Multi-Step Agent (Sequential Processing)

**Use Case**: Data extraction → transformation → formatting, pipeline processing
**Components**: Input → Extract → Transform → Format → Output

```python
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.graph import START, StateGraph, END
from uipath_langchain.chat import UiPathChat
from pydantic import BaseModel
from typing import List, Dict, Any

class Input(BaseModel):
    document: str

class State(BaseModel):
    document: str
    extracted_data: Dict[str, Any] = {}
    transformed_data: List[Dict] = []
    formatted_output: str = ""

class Output(BaseModel):
    result: str
    data: List[Dict]

llm = UiPathChat(model="gpt-4o-2024-08-06")

async def extract_node(state: State) -> State:
    response = await llm.ainvoke([
        SystemMessage("Extract key-value pairs from the document. Return as JSON."),
        HumanMessage(state.document)
    ])
    extracted = {"title": "Sample", "items": []}
    return State(document=state.document, extracted_data=extracted)

async def transform_node(state: State) -> State:
    transformed = [{"id": i, "value": item} for i, item in enumerate(state.extracted_data.get("items", []))]
    return State(
        document=state.document,
        extracted_data=state.extracted_data,
        transformed_data=transformed
    )

async def format_node(state: State) -> State:
    formatted = f"Found {len(state.transformed_data)} items"
    return State(
        document=state.document,
        extracted_data=state.extracted_data,
        transformed_data=state.transformed_data,
        formatted_output=formatted
    )

async def output_node(state: State) -> Output:
    return Output(result=state.formatted_output, data=state.transformed_data)

builder = StateGraph(State, input=Input, output=Output)
builder.add_node("extract", extract_node)
builder.add_node("transform", transform_node)
builder.add_node("format", format_node)
builder.add_node("output", output_node)

builder.add_edge(START, "extract")
builder.add_edge("extract", "transform")
builder.add_edge("transform", "format")
builder.add_edge("format", "output")
builder.add_edge("output", END)

graph = builder.compile()
```

**Key Points**:
- Each node does one thing well
- State accumulates results from each step
- Each node receives and returns State (except final node)
- Use descriptive node names matching the operation

---

### Pattern 3: RAG Agent (Context Grounding)

**Use Case**: Question answering from documents, knowledge base queries
**Components**: Input → Retrieve Context → Generate Answer → Output

```python
from langchain_core.messages import HumanMessage
from langgraph.graph import START, StateGraph, END
from uipath_langchain.chat import UiPathChat
from uipath_langchain.retrievers import ContextGroundingRetriever
from pydantic import BaseModel
from typing import List

class Input(BaseModel):
    query: str

class State(BaseModel):
    query: str
    context: str = ""
    answer: str = ""

class Output(BaseModel):
    answer: str
    sources: List[str] = []

llm = UiPathChat(model="gpt-4o-2024-08-06")
retriever = ContextGroundingRetriever(
    index_name="CompanyKnowledgeBase",
    number_of_results=3
)

async def retrieve_context(state: State) -> State:
    docs = await retriever.ainvoke(state.query)
    context = "\n\n".join([doc.page_content for doc in docs])
    return State(query=state.query, context=context)

async def generate_answer(state: State) -> State:
    prompt = f"""Based on the following context, answer the question.

Context:
{state.context}

Question: {state.query}

Provide a clear, accurate answer based only on the context provided."""

    response = await llm.ainvoke([HumanMessage(prompt)])
    return State(query=state.query, context=state.context, answer=response.content)

async def output_node(state: State) -> Output:
    sources = ["Source 1", "Source 2"]
    return Output(answer=state.answer, sources=sources)

builder = StateGraph(State, input=Input, output=Output)
builder.add_node("retrieve", retrieve_context)
builder.add_node("generate", generate_answer)
builder.add_node("output", output_node)

builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "generate")
builder.add_edge("generate", "output")
builder.add_edge("output", END)

graph = builder.compile()
```

**Key Points**:
- Use `ContextGroundingRetriever` for semantic search
- Pass retrieved context to LLM prompt
- Include context in prompt with clear instructions
- Track sources for transparency

---

### Pattern 4: ReAct Agent (Tool Use)

**Use Case**: Research, external API calls, multi-step reasoning
**Components**: Input → ReAct Agent (tools) → Output

```python
from langgraph.graph import START, StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool
from uipath_langchain.chat import UiPathChat
from uipath import UiPath
from pydantic import BaseModel

sdk = UiPath()

class Input(BaseModel):
    task: str

class State(BaseModel):
    task: str
    result: str = ""

class Output(BaseModel):
    result: str

@tool
def search_documents(query: str) -> str:
    """Search internal knowledge base for information."""
    hits = sdk.context_grounding.search(
        name="KnowledgeBase",
        query=query,
        number_of_results=3
    )
    return "\n".join([hit.content for hit in hits])

@tool
def get_config(key: str) -> str:
    """Retrieve configuration value from assets."""
    asset = sdk.assets.retrieve(name=key)
    return asset.value

llm = UiPathChat(model="gpt-4o-2024-08-06")
react_agent = create_react_agent(
    llm,
    tools=[search_documents, get_config],
    prompt="You are a helpful assistant. Use tools to answer questions accurately."
)

async def agent_node(state: State) -> State:
    result = await react_agent.ainvoke({"messages": [("user", state.task)]})
    final_message = result["messages"][-1].content
    return State(task=state.task, result=final_message)

async def output_node(state: State) -> Output:
    return Output(result=state.result)

builder = StateGraph(State, input=Input, output=Output)
builder.add_node("agent", agent_node)
builder.add_node("output", output_node)

builder.add_edge(START, "agent")
builder.add_edge("agent", "output")
builder.add_edge("output", END)

graph = builder.compile()
```

**Key Points**:
- Use `@tool` decorator for custom tools
- Provide clear docstrings - LLM uses them to decide when to call
- `create_react_agent` handles tool calling automatically
- Agent iterates: think → act → observe until task complete

---

### Pattern 5: Conditional Routing Agent

**Use Case**: Different processing paths based on input or intermediate results
**Components**: Input → Classify → Route to appropriate processing → Output

```python
from langchain_core.messages import HumanMessage
from langgraph.graph import START, StateGraph, END
from uipath_langchain.chat import UiPathChat
from pydantic import BaseModel, Field
from typing import Literal

class Input(BaseModel):
    request: str

class Classification(BaseModel):
    category: Literal["urgent", "normal", "info_request"] = Field(
        description="Category of the request"
    )

class State(BaseModel):
    request: str
    category: str = ""
    result: str = ""

class Output(BaseModel):
    result: str
    category: str

llm = UiPathChat(model="gpt-4o-2024-08-06")
classifier = llm.with_structured_output(Classification)

async def classify_node(state: State) -> State:
    classification = await classifier.ainvoke(
        f"Classify this request: {state.request}"
    )
    return State(request=state.request, category=classification.category)

async def handle_urgent(state: State) -> State:
    response = await llm.ainvoke([
        HumanMessage(f"URGENT: {state.request}. Provide immediate action steps.")
    ])
    return State(request=state.request, category=state.category, result=response.content)

async def handle_normal(state: State) -> State:
    response = await llm.ainvoke([
        HumanMessage(f"Process this request: {state.request}")
    ])
    return State(request=state.request, category=state.category, result=response.content)

async def handle_info(state: State) -> State:
    result = "Information retrieved from knowledge base."
    return State(request=state.request, category=state.category, result=result)

async def output_node(state: State) -> Output:
    return Output(result=state.result, category=state.category)

def route_by_category(state: State) -> str:
    if state.category == "urgent":
        return "urgent"
    elif state.category == "normal":
        return "normal"
    else:
        return "info"

builder = StateGraph(State, input=Input, output=Output)
builder.add_node("classify", classify_node)
builder.add_node("urgent", handle_urgent)
builder.add_node("normal", handle_normal)
builder.add_node("info", handle_info)
builder.add_node("output", output_node)

builder.add_edge(START, "classify")
builder.add_conditional_edges(
    "classify",
    route_by_category,
    {"urgent": "urgent", "normal": "normal", "info": "info"}
)
builder.add_edge("urgent", "output")
builder.add_edge("normal", "output")
builder.add_edge("info", "output")
builder.add_edge("output", END)

graph = builder.compile()
```

**Key Points**:
- Use `.with_structured_output()` for classification
- `add_conditional_edges` with routing function
- Routing function returns node name as string
- All paths must eventually converge to output

---

### Pattern 6: Queue Processing Agent

**Use Case**: Batch processing, transactional work, reliable processing
**Components**: Input → Claim Transaction → Process → Mark Complete → Output

```python
from langchain_core.messages import HumanMessage
from langgraph.graph import START, StateGraph, END
from uipath_langchain.chat import UiPathChat
from uipath import UiPath
from pydantic import BaseModel
from typing import Dict, Any, Optional

sdk = UiPath()

class Input(BaseModel):
    queue_name: str

class State(BaseModel):
    queue_name: str
    transaction_id: Optional[str] = None
    transaction_data: Dict[str, Any] = {}
    processed_result: Dict[str, Any] = {}
    status: str = "pending"

class Output(BaseModel):
    status: str
    result: Dict[str, Any]

llm = UiPathChat(model="gpt-4o-2024-08-06")

async def claim_transaction(state: State) -> State:
    trx = sdk.queues.create_transaction_item(name=state.queue_name)

    if not trx:
        return State(
            queue_name=state.queue_name,
            status="no_transactions"
        )

    return State(
        queue_name=state.queue_name,
        transaction_id=trx.id,
        transaction_data=trx.specific_content,
        status="claimed"
    )

async def process_transaction(state: State) -> State:
    if state.status != "claimed":
        return state

    try:
        response = await llm.ainvoke([
            HumanMessage(f"Process this data: {state.transaction_data}")
        ])

        result = {
            "processed": True,
            "output": response.content,
            "transaction_id": state.transaction_id
        }

        return State(
            queue_name=state.queue_name,
            transaction_id=state.transaction_id,
            transaction_data=state.transaction_data,
            processed_result=result,
            status="processed"
        )
    except Exception as e:
        return State(
            queue_name=state.queue_name,
            transaction_id=state.transaction_id,
            transaction_data=state.transaction_data,
            processed_result={"error": str(e)},
            status="failed"
        )

async def mark_complete(state: State) -> State:
    if state.status == "no_transactions":
        return state

    try:
        if state.status == "processed":
            sdk.queues.complete_transaction_item(
                state.transaction_id,
                {"status": "Successful", "result": state.processed_result}
            )
        else:
            sdk.queues.complete_transaction_item(
                state.transaction_id,
                {
                    "status": "Failed",
                    "is_successful": False,
                    "processing_exception": state.processed_result.get("error", "Unknown error")
                }
            )

        return state
    except Exception as e:
        return state

async def output_node(state: State) -> Output:
    return Output(status=state.status, result=state.processed_result)

builder = StateGraph(State, input=Input, output=Output)
builder.add_node("claim", claim_transaction)
builder.add_node("process", process_transaction)
builder.add_node("complete", mark_complete)
builder.add_node("output", output_node)

builder.add_edge(START, "claim")
builder.add_edge("claim", "process")
builder.add_edge("process", "complete")
builder.add_edge("complete", "output")
builder.add_edge("output", END)

graph = builder.compile()
```

**Key Points**:
- Always claim transaction before processing
- Always mark complete/failed (even on errors)
- Use try/except to catch processing failures
- Include error details in failure status
- Check if transaction exists before processing

---

### Pattern 7: Asset Configuration Agent

**Use Case**: Agents that need configuration or secrets from UiPath Assets
**Components**: Load Config → Process with Config → Output

```python
from langchain_core.messages import HumanMessage
from langgraph.graph import START, StateGraph, END
from uipath_langchain.chat import UiPathChat
from uipath import UiPath
from pydantic import BaseModel
from typing import Dict, Any

sdk = UiPath()

class Input(BaseModel):
    task: str

class State(BaseModel):
    task: str
    config: Dict[str, Any] = {}
    result: str = ""

class Output(BaseModel):
    result: str

llm = UiPathChat(model="gpt-4o-2024-08-06")

async def load_config(state: State) -> State:
    try:
        api_url = sdk.assets.retrieve(name="ApiEndpoint")
        max_retries = sdk.assets.retrieve(name="MaxRetries")

        config = {
            "api_url": api_url.value,
            "max_retries": int(max_retries.value)
        }

        try:
            cred = sdk.assets.retrieve_credential(name="ApiCredential")
            config["username"] = cred.username
            config["password"] = cred.password
        except ValueError:
            pass

        return State(task=state.task, config=config)

    except Exception as e:
        return State(
            task=state.task,
            config={"api_url": "https://default.api.com", "max_retries": 3}
        )

async def process_with_config(state: State) -> State:
    prompt = f"""Task: {state.task}
Configuration:
- API URL: {state.config.get('api_url')}
- Max Retries: {state.config.get('max_retries')}

Process the task using the provided configuration."""

    response = await llm.ainvoke([HumanMessage(prompt)])
    return State(task=state.task, config=state.config, result=response.content)

async def output_node(state: State) -> Output:
    return Output(result=state.result)

builder = StateGraph(State, input=Input, output=Output)
builder.add_node("load_config", load_config)
builder.add_node("process", process_with_config)
builder.add_node("output", output_node)

builder.add_edge(START, "load_config")
builder.add_edge("load_config", "process")
builder.add_edge("process", "output")
builder.add_edge("output", END)

graph = builder.compile()
```

**Key Points**:
- Load assets at start of execution
- Use try/except for asset retrieval (may not exist)
- Provide sensible defaults if assets missing
- Credentials only available in robot context
- Pass config through state to all nodes

---

## State Management Patterns

### Simple Pass-Through State
```python
class State(BaseModel):
    input_data: str
    result: str = ""
```

### Accumulating Results State
```python
class State(BaseModel):
    query: str
    results: List[str] = []  # Accumulate across nodes
    metadata: Dict[str, Any] = {}
```

### Error Tracking State
```python
class State(BaseModel):
    data: str
    result: str = ""
    error: Optional[str] = None
    retry_count: int = 0
```

### Branching State (for conditional routing)
```python
class State(BaseModel):
    input: str
    classification: str = ""  # Used for routing
    processing_path: str = ""
    result: str = ""
```

---

## Error Handling Patterns

### Pattern: LLM Call with Retry
```python
async def safe_llm_call(state: State) -> State:
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await llm.ainvoke(messages)
            return State(result=response.content, error=None)
        except Exception as e:
            if attempt == max_retries - 1:
                return State(result="", error=str(e))
            await asyncio.sleep(2 ** attempt)
```

### Pattern: Asset Retrieval with Fallback
```python
async def get_config_with_fallback(state: State) -> State:
    try:
        asset = sdk.assets.retrieve(name="Config")
        config = asset.value
    except Exception as e:
        config = "default_value"

    return State(config=config)
```

### Pattern: Transaction with Error Marking
```python
async def process_transaction_safely(state: State) -> State:
    try:
        result = await process_data(state.data)

        sdk.queues.complete_transaction_item(
            state.transaction_id,
            {"status": "Successful", "result": result}
        )
        return State(status="success", result=result)

    except Exception as e:
        sdk.queues.complete_transaction_item(
            state.transaction_id,
            {
                "status": "Failed",
                "is_successful": False,
                "processing_exception": str(e)
            }
        )
        return State(status="failed", error=str(e))
```

### Pattern: File Operation with Cleanup
```python
async def process_file_safely(state: State) -> State:
    file_path = None
    try:
        file_path = await sdk.buckets.download_async(
            name="InputBucket",
            blob_file_path=state.file_name,
            destination_path=f"temp_{state.file_name}"
        )

        with open(file_path, 'r') as f:
            data = f.read()

        result = await process_data(data)
        return State(result=result)

    except Exception as e:
        return State(error=str(e))

    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
```

---

## Best Practices

### 1. Always Use Async/Await
```python
# ✅ Good
async def node(state: State) -> State:
    result = await llm.ainvoke(messages)
    return State(result=result.content)

# ❌ Bad - blocks execution
def node(state: State) -> State:
    result = llm.invoke(messages)
    return State(result=result.content)
```

### 2. Handle Errors Gracefully
```python
async def node(state: State) -> State:
    try:
        result = await process(state.data)
        return State(result=result)
    except Exception as e:
        return State(error=str(e))
```

### 3. Type-Safe Pydantic Models
```python
from pydantic import BaseModel, Field, validator

class Input(BaseModel):
    text: str = Field(..., min_length=1, max_length=10000)
    priority: int = Field(default=5, ge=1, le=10)

    @validator('text')
    def text_not_empty(cls, v):
        if not v.strip():
            raise ValueError('Text cannot be empty')
        return v.strip()
```

### 4. Structured LLM Outputs
```python
from pydantic import BaseModel, Field

class Analysis(BaseModel):
    sentiment: Literal["positive", "negative", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    key_points: List[str]

structured_llm = llm.with_structured_output(Analysis)
result = await structured_llm.ainvoke(text)
# result is validated Analysis object
```

### 5. Environment Configuration
```python
import os
from dotenv import load_dotenv

load_dotenv()

# ✅ Good - from environment
FOLDER_PATH = os.environ.get("UIPATH_FOLDER_PATH", "Shared")
API_KEY = os.environ.get("EXTERNAL_API_KEY")

# ❌ Bad - hardcoded
API_KEY = "sk-1234567890"
```

### 6. Resource Cleanup
```python
async def node(state: State) -> State:
    resources = []
    try:
        file = await download_file(state.file_id)
        resources.append(file)

        result = await process(file)
        return State(result=result)

    finally:
        for resource in resources:
            await cleanup(resource)
```

---

---

---

## Quick API Reference

This section provides a concise reference for the most commonly used UiPath SDK methods.

### SDK Initialization

Initialize the UiPath SDK client

```python
from uipath import UiPath

# Initialize with environment variables
sdk = UiPath()

# Or with explicit credentials
sdk = UiPath(base_url="https://cloud.uipath.com/...", secret="your_token")
```

### Actions

Actions service

```python
# Creates a new action synchronously.
sdk.actions.create(title, data=None, app_name=None, app_key=None, app_folder_path=None, app_folder_key=None, app_version=1, assignee=None)

# Creates a new action asynchronously.
sdk.actions.create_async(title, data=None, app_name=None, app_key=None, app_folder_path=None, app_folder_key=None, app_version=1, assignee=None)

# Retrieves an action by its key synchronously.
sdk.actions.retrieve(action_key, app_folder_path="", app_folder_key="")

```

### Api Client

Api Client service

```python
```

### Assets

Assets service

```python
# Retrieve an asset by its name.
sdk.assets.retrieve(name, folder_key=None, folder_path=None)

# Asynchronously retrieve an asset by its name.
sdk.assets.retrieve_async(name, folder_key=None, folder_path=None)

# Gets a specified Orchestrator credential.
sdk.assets.retrieve_credential(name, folder_key=None, folder_path=None)

```

### Attachments

Attachments service

```python
# Delete an attachment.
sdk.attachments.delete(key, folder_key=None, folder_path=None)

# Delete an attachment asynchronously.
sdk.attachments.delete_async(key, folder_key=None, folder_path=None)

# Download an attachment.
sdk.attachments.download(key, destination_path, folder_key=None, folder_path=None)

```

### Buckets

Buckets service

```python
# Download a file from a bucket.
sdk.buckets.download(name=None, key=None, blob_file_path, destination_path, folder_key=None, folder_path=None)

# Download a file from a bucket asynchronously.
sdk.buckets.download_async(name=None, key=None, blob_file_path, destination_path, folder_key=None, folder_path=None)

# Retrieve bucket information by its name.
sdk.buckets.retrieve(name=None, key=None, folder_key=None, folder_path=None)

```

### Connections

Connections service

```python
# Lists all connections with optional filtering.
sdk.connections.list(name=None, folder_path=None, folder_key=None, connector_key=None, skip=None, top=None)

# Asynchronously lists all connections with optional filtering.
sdk.connections.list_async(name=None, folder_path=None, folder_key=None, connector_key=None, skip=None, top=None)

# Retrieve connection details by its key.
sdk.connections.retrieve(key)

```

### Context Grounding

Context Grounding service

```python
# Add content to the index.
sdk.context_grounding.add_to_index(name, blob_file_path, content_type=None, content=None, source_path=None, folder_key=None, folder_path=None, ingest_data=True)

# Asynchronously add content to the index.
sdk.context_grounding.add_to_index_async(name, blob_file_path, content_type=None, content=None, source_path=None, folder_key=None, folder_path=None, ingest_data=True)

# Create a new context grounding index.
sdk.context_grounding.create_index(name, source, description=None, cron_expression=None, time_zone_id=None, advanced_ingestion=True, preprocessing_request="#UiPath.Vdbs.Domain.Api.V20Models.LLMV4PreProcessingRequest", folder_key=None, folder_path=None)

```

### Documents

Documents service

```python
# Create a validation action for a document based on the extraction response. More details about validation actions can be found in the [official documentation](https://docs.uipath.com/ixp/automation-cloud/latest/user-guide/validating-extractions).
sdk.documents.create_validation_action(action_title, action_priority, action_catalog, action_folder, storage_bucket_name, storage_bucket_directory_path, extraction_response)

# Asynchronously create a validation action for a document based on the extraction response.
sdk.documents.create_validation_action_async(action_title, action_priority, action_catalog, action_folder, storage_bucket_name, storage_bucket_directory_path, extraction_response)

# Extract predicted data from a document using an IXP project.
sdk.documents.extract(project_name, tag, file=None, file_path=None)

```

### Entities

Entities service

```python
# Delete multiple records from an entity in a single batch operation.
sdk.entities.delete_records(entity_key, record_ids)

# Asynchronously delete multiple records from an entity in a single batch operation.
sdk.entities.delete_records_async(entity_key, record_ids)

# Insert multiple records into an entity in a single batch operation.
sdk.entities.insert_records(entity_key, records, schema=None)

```

### Folders

Folders service

```python
# Retrieve the folder key by folder path with pagination support.
sdk.folders.retrieve_key(folder_path)

```

### Jobs

Jobs service

```python
# Create and upload an attachment, optionally linking it to a job.
sdk.jobs.create_attachment(name, content=None, source_path=None, job_key=None, category=None, folder_key=None, folder_path=None)

# Create and upload an attachment asynchronously, optionally linking it to a job.
sdk.jobs.create_attachment_async(name, content=None, source_path=None, job_key=None, category=None, folder_key=None, folder_path=None)

# Get the actual output data, downloading from attachment if necessary.
sdk.jobs.extract_output(job)

```

### Llm

Llm service

```python
# Generate chat completions using UiPath's normalized LLM Gateway API.
sdk.llm.chat_completions(messages, model="gpt-4o-mini-2024-07-18", max_tokens=4096, temperature=0, n=1, frequency_penalty=0, presence_penalty=0, top_p=1, top_k=None, tools=None, tool_choice=None, response_format=None, api_version="2024-08-01-preview")

```

### Llm Openai

Llm Openai service

```python
# Generate chat completions using UiPath's LLM Gateway service.
sdk.llm_openai.chat_completions(messages, model="gpt-4o-mini-2024-07-18", max_tokens=4096, temperature=0, response_format=None, api_version="2024-10-21")

# Generate text embeddings using UiPath's LLM Gateway service.
sdk.llm_openai.embeddings(input, embedding_model="text-embedding-ada-002", openai_api_version="2024-10-21")

```

### Processes

Processes service

```python
# Start execution of a process by its name.
sdk.processes.invoke(name, input_arguments=None, folder_key=None, folder_path=None)

# Asynchronously start execution of a process by its name.
sdk.processes.invoke_async(name, input_arguments=None, folder_key=None, folder_path=None)

```

### Queues

Queues service

```python
# Completes a transaction item with the specified result.
sdk.queues.complete_transaction_item(transaction_key, result)

# Asynchronously completes a transaction item with the specified result.
sdk.queues.complete_transaction_item_async(transaction_key, result)

# Creates a new queue item in the Orchestrator.
sdk.queues.create_item(item)

```

For complete API documentation, visit: https://uipath.github.io/uipath-python/


---

## CLI Commands Reference

**UiPath Python SDK Version:** `2.1.78`

The UiPath Python SDK provides a comprehensive CLI for managing coded agents and automation projects.

### `uipath new`

Generate a quick-start project.

**Arguments:**

- `name` (optional)

**Example:**

```bash
uipath new my-agent
```

### `uipath init`

Create uipath.json with input/output schemas and bindings.

**Arguments:**

- `entrypoint` (optional)

**Options:**

- `--infer-bindings` (flag): Infer bindings from the script.

**Example:**

```bash
uipath init
```

### `uipath run`

Execute the project.

**Arguments:**

- `entrypoint` (optional)
- `input` (optional)

**Options:**

- `--resume` (flag): Resume execution from a previous state
- `-f`, `--file`: File path for the .json input
- `--input-file`: Alias for '-f/--file' arguments
- `--output-file`: File path where the output will be written
- `--debug` (flag): Enable debugging with debugpy. The process will wait for a debugger to attach.
- `--debug-port` (default: `5678`): Port for the debug server (default: 5678)

**Example:**

```bash
uipath run main.py '{"input": "value"}'
```

### `uipath pack`

Pack the project.

**Arguments:**

- `root` (optional)

**Options:**

- `--nolock` (flag): Skip running uv lock and exclude uv.lock from the package

**Example:**

```bash
uipath pack
```

### `uipath publish`

Publish the package.

**Options:**

- `--tenant`, `-t` (flag): Whether to publish to the tenant package feed
- `--my-workspace`, `-w` (flag): Whether to publish to the personal workspace

**Example:**

```bash
uipath publish
```

### `uipath deploy`

Pack and publish the project.

**Arguments:**

- `root` (optional)

**Options:**

- `--tenant`, `-t` (flag): Whether to publish to the tenant package feed
- `--my-workspace`, `-w` (flag): Whether to publish to the personal workspace

**Example:**

```bash
uipath deploy my-process
```

### `uipath invoke`

Invoke an agent published in my workspace.

**Arguments:**

- `entrypoint` (optional)
- `input` (optional)

**Options:**

- `-f`, `--file`: File path for the .json input

**Example:**

```bash
uipath invoke my-process '{"input": "value"}'
```

### `uipath push`

Push local project files to Studio Web Project.

    This command pushes the local project files to a UiPath Studio Web project.
    It ensures that the remote project structure matches the local files by:
    - Updating existing files that have changed
    - Uploading new files
    - Deleting remote files that no longer exist locally
    - Optionally managing the UV lock file

    Args:
        root: The root directory of the project
        nolock: Whether to skip UV lock operations and exclude uv.lock from push

    Environment Variables:
        UIPATH_PROJECT_ID: Required. The ID of the UiPath Cloud project

    Example:
        $ uipath push
        $ uipath push --nolock
    

**Arguments:**

- `root` (optional)

**Options:**

- `--nolock` (flag): Skip running uv lock and exclude uv.lock from the package

**Example:**

```bash
uipath push
```

### `uipath pull`

Pull remote project files from Studio Web Project.

    This command pulls the remote project files from a UiPath Studio Web project.
    It downloads files from the source_code and evals folders, maintaining the
    folder structure locally. Files are compared using hashes before overwriting,
    and user confirmation is required for differing files.

    Args:
        root: The root directory to pull files into

    Environment Variables:
        UIPATH_PROJECT_ID: Required. The ID of the UiPath Studio Web project

    Example:
        $ uipath pull
        $ uipath pull /path/to/project
    

**Arguments:**

- `root` (optional)

**Example:**

```bash
uipath pull my-process
```

### `uipath eval`

Run an evaluation set against the agent.

    Args:
        entrypoint: Path to the agent script to evaluate (optional, will auto-discover if not specified)
        eval_set: Path to the evaluation set JSON file (optional, will auto-discover if not specified)
        eval_ids: Optional list of evaluation IDs
        workers: Number of parallel workers for running evaluations
        no_report: Do not report the evaluation results
    

**Arguments:**

- `entrypoint` (optional)
- `eval_set` (optional)

**Options:**

- `--no-report` (flag): Do not report the evaluation results
- `--workers` (default: `8`): Number of parallel workers for running evaluations (default: 8)
- `--output-file`: File path where the output will be written

**Example:**

```bash
uipath eval
```

### `uipath dev`

Launch interactive debugging interface.

**Arguments:**

- `interface` (optional)

**Options:**

- `--debug` (flag): Enable debugging with debugpy. The process will wait for a debugger to attach.
- `--debug-port` (default: `5678`): Port for the debug server (default: 5678)

**Example:**

```bash
uipath dev
```

### `uipath auth`

Authenticate with UiPath Cloud Platform.

    The domain for authentication is determined by the UIPATH_URL environment variable if set.
    Otherwise, it can be specified with --cloud (default), --staging, or --alpha flags.

    Interactive mode (default): Opens browser for OAuth authentication.
    Unattended mode: Use --client-id, --client-secret, --base-url and --scope for client credentials flow.

    Network options:
    - Set HTTP_PROXY/HTTPS_PROXY/NO_PROXY environment variables for proxy configuration
    - Set REQUESTS_CA_BUNDLE to specify a custom CA bundle for SSL verification
    - Set UIPATH_DISABLE_SSL_VERIFY to disable SSL verification (not recommended)
    

**Options:**

- `--cloud` (flag): Use production environment
- `--staging` (flag): Use staging environment
- `--alpha` (flag): Use alpha environment
- `-f`, `--force` (flag): Force new token
- `--client-id`: Client ID for client credentials authentication (unattended mode)
- `--client-secret`: Client secret for client credentials authentication (unattended mode)
- `--base-url`: Base URL for the UiPath tenant instance (required for client credentials)
- `--tenant`: Tenant name within UiPath Automation Cloud
- `--scope` (default: `OR.Execution`): Space-separated list of OAuth scopes to request (e.g., 'OR.Execution OR.Queues'). Defaults to 'OR.Execution'

**Example:**

```bash
uipath auth login
```

---

For more information on any command, run:
```bash
uipath <command> --help
```
