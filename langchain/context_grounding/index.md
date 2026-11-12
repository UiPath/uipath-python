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
from uipath_langchain.retrievers import ContextGroundingRetriever

retriever = ContextGroundingRetriever(index_name = "Company Policy Context")
print(retriever.invoke("What is the company policy on remote work?"))
```

### Integration with LangChain Tools

You can easily integrate the retriever with LangChain's tool system:

```
from langchain.agents import create_agent
from langchain_core.tools.retriever import create_retriever_tool
from uipath_langchain.retrievers import ContextGroundingRetriever

retriever = ContextGroundingRetriever(index_name = "Company Policy Context")
retriever_tool = create_retriever_tool(
    retriever,
    "ContextforInvoiceDisputeInvestigation",
   """
   Use this tool to search the company internal documents for information about policies around dispute resolution.
   Use a meaningful query to load relevant information from the documents. Save the citation for later use.
   """
)

# You can use the tool in your agents
model = OpenAI()
tools = [retriever_tool]
agent = create_agent(model, tools, system_prompt="Answer user questions as best as you can using the search tool.")
```

### Advanced Usage

For complex applications, the retriever can be combined with other LangChain components to create robust document QA systems, agents, or knowledge bases.

## ContextGroundingVectorStore

`ContextGroundingVectorStore` is a vector store implementation designed for context-aware document retrieval. It allows you to perform semantic searches and create retrieval chains with language models.

### Searching Documents

The vector store supports various search methods:

```
from uipath_langchain.vectorstores.context_grounding_vectorstore import ContextGroundingVectorStore

vectorstore = ContextGroundingVectorStore(index_name="Company policy")

# Perform semantic searches with distance scores
docs_with_scores = vectorstore.asimilarity_search_with_score(query="What is the company policy on data storage?", k=5)

# Perform a similarity search with relevance scores
docs_with_relevance_scores = await vectorstore.asimilarity_search_with_relevance_scores(query=query, k=5)
```

### Creating a Retrieval Chain

You can integrate the vector store into a retrieval chain with a language model:

```
# Run a retrieval chain
model = UiPathAzureChatOpenAI(model="gpt-4.1-mini-2025-04-14", max_retries=3)
retrieval_chain = create_retrieval_chain(vectorstore=vectorstore, model=model)

query = "What is the ECCN for a laptop?"
result = retrieval_chain(query)
```
