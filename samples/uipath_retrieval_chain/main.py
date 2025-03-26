"""Example demonstrating how to use the ContextGroundingVectorStore class with LangChain."""

import argparse
import asyncio
from pprint import pprint
from typing import Any

from dotenv import find_dotenv, load_dotenv
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.vectorstores import VectorStore
from uipath_langchain.chat.models import UiPathAzureChatOpenAI
from uipath_langchain.vectorstores.context_grounding_vectorstore import (
    ContextGroundingVectorStore,
)


def create_retrieval_chain(vectorstore: VectorStore, model: BaseChatModel, k: int = 3):
    """Create a retrieval chain using a vector store.

    Args:
        vectorstore: Vector store to use for the chain
        model: LangChain language model to use for the chain

    Returns:
        A retrieval chain ready to answer questions
    """
    # Create a retriever from the vector store
    retriever = vectorstore.as_retriever(
        search_kwargs={"k": k},
    )

    # Create a prompt template
    template = """Answer the question based on the following context:
    {context}
    Question: {question}
    """
    prompt = ChatPromptTemplate.from_template(template)

    # Create the retrieval chain
    chain = (
        {"context": retriever, "question": RunnablePassthrough()}
        | prompt
        | model
        | StrOutputParser()
    )

    # Return a function that will run the chain and include source documents
    def retrieval_chain(query: str) -> dict[str, Any]:
        # Get documents separately to include them in the result
        docs = retriever.invoke(query)
        # Run the chain
        answer = chain.invoke(query)
        # Return combined result
        return {"result": answer, "source_documents": docs}

    return retrieval_chain


async def main(index_name: str, query: str, k: int = 3):
    load_dotenv(find_dotenv())

    """Run a simple example of ContextGroundingVectorStore."""
    vectorstore = ContextGroundingVectorStore(
        index_name=index_name,
    )

    # Example query
    query = "What is the ECCN for a laptop?"

    # Perform semantic searches with distance scores
    docs_with_scores = await vectorstore.asimilarity_search_with_score(query=query, k=5)
    print("==== Docs with distance scores ====")
    pprint(
        [
            {"page_content": doc.page_content, "distance_score": distance_score}
            for doc, distance_score in docs_with_scores
        ]
    )

    # Perform a similarity search with relevance scores
    docs_with_relevance_scores = (
        await vectorstore.asimilarity_search_with_relevance_scores(query=query, k=5)
    )
    print("==== Docs with relevance scores ====")
    pprint(
        [
            {"page_content": doc.page_content, "relevance_score": relevance_score}
            for doc, relevance_score in docs_with_relevance_scores
        ]
    )

    # Run a retrieval chain
    model = UiPathAzureChatOpenAI(
        model="gpt-4o-2024-08-06",
        max_retries=3,
    )

    retrieval_chain = create_retrieval_chain(
        vectorstore=vectorstore,
        model=model,
    )

    # Run a retrieval chain
    result = retrieval_chain(query)
    print("==== Retrieval chain result ====")
    print(f"Query: {query}")
    print(f"Answer: {result['result']}")
    print("\nSource Documents:")
    for i, doc in enumerate(result["source_documents"]):
        print(f"\nDocument {i + 1}:")
        print(f"Content: {doc.page_content[:100]}...")
        print(
            f"Source: {doc.metadata.get('source', 'N/A')}, Page Number: {doc.metadata.get('page_number', '0')}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--index_name", type=str, default="ECCN", help="The name of the index to use"
    )
    parser.add_argument(
        "--query",
        type=str,
        default="What is the ECCN for a laptop?",
        help="The query for which documents will be retrieved",
    )
    parser.add_argument(
        "--k", type=int, default=3, help="The number of documents to retrieve"
    )
    args = parser.parse_args()
    asyncio.run(main(args.index_name, args.query, args.k))
