# Context Grounding

Context Grounding Service allows you to:

- Search through indexed documents using natural language queries
- Ground LLM responses in your organization's specific information
- Retrieve context-relevant documents for various applications

You will need to create an index in `Context Grounding` to use this feature. To create an index go to organization `Orchestrator` -> the folder where you'd like to create an index -> `Indexes`. There you can create a new index from a storage bucket which you've added documents to. See the full documentation [here](https://docs.uipath.com/automation-cloud/automation-cloud/latest/admin-guide/about-context-grounding) for more details.

## ContextGroundingRetriever

The `ContextGroundingRetriever` is a document retrieval system that uses vector search to efficiently find and retrieve relevant information from your document store.

### Basic Usage

Create a simple retriever by specifying an index name:

```
from uipath_llamaindex.retrievers import ContextGroundingRetriever

retriever = ContextGroundingRetriever(index_name = "Company Policy Context")
print(retriever.retrieve("What is the company policy on remote work?"))
```

## ContextGroundingQueryEngine

Query engines are interfaces that allows you to ask question over your data. The `ContextGroundingQueryEngine` is a query engine system that leverages the `ContextGroundingRetriever`.

### Basic Usage

Create a simple query engine by specifying an index name and a synthesizer strategy:

```
from uipath_llamaindex.query_engines import ContextGroundingQueryEngine
from llama_index.core.response_synthesizers.type import ResponseMode
from llama_index.core import get_response_synthesizer

synthesizer = get_response_synthesizer(ResponseMode.SIMPLE_SUMMARIZE)
query_engine = ContextGroundingQueryEngine(index_name = "Company Policy Context", response_synthesizer=synthesizer)
print(query_engine.query("What is the company policy on remote work?"))
```

### Integration with LlamaIndex Tools

You can easily integrate the query engine with LlamaIndex's tool system:

```
from uipath_llamaindex.query_engines import ContextGroundingQueryEngine
from llama_index.core.response_synthesizers.type import ResponseMode
from llama_index.core import get_response_synthesizer

query_engine = ContextGroundingQueryEngine(
    index_name="Company Policy Context",
    response_synthesizer=get_response_synthesizer(ResponseMode.REFINE),
)
query_engine_tools = [QueryEngineTool(
            query_engine=query_engine,
            metadata=ToolMetadata(
                name="Company policy",
                description="Information about general company policy",
            )
        )]
# You can use the tool in your agents
react_agent = ReActAgent.from_tools(query_engine_tools)
response = react_agent.chat("Answer user questions as best as you can using the query engine tool.")
```

Tip

Check our [travel-helper-RAG-agent sample](https://github.com/UiPath/uipath-integrations-python/tree/main/packages/uipath-llamaindex/samples/travel-helper-RAG-agent) to see context grounding query engines in action.
