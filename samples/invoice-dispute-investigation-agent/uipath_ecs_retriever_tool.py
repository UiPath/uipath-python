from langchain.tools.retriever import create_retriever_tool
from uipath_langchain.retrievers import ContextGroundingRetriever
from os import environ as env

retriever = ContextGroundingRetriever(index_name=f"{env.get('UIPATH_ECS_CONTEXT')}")
retriever_tool = create_retriever_tool(
    retriever,
    "ContextforInvoiceDisputeInvestigation",
   """
   Use this tool to search the company internal documents for information about policies around dispute resolution.
   Use a meaningful query to load relevant information from the documents. Save the citation for later use.
   """
)
