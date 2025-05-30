from typing import Optional
import time
from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command
from pydantic import BaseModel
from uipath import UiPath
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from uipath.models import ContextGroundingIndex

uipath = UiPath()
tavily_tool = TavilySearchResults(max_results=5)
anthropic_model = "claude-3-5-sonnet-latest"


llm = ChatAnthropic(model=anthropic_model)


class GraphInput(BaseModel):
    search_instructions: str
    index_name: str
    index_folder_path: str

class GraphState(BaseModel):
    search_instructions: str
    web_results: str
    index_name: str
    index_folder_path: str
    file_name: Optional[str]
    index: Optional[ContextGroundingIndex]

def prepare_input(state: GraphInput) -> GraphState:
    return GraphState(
        search_instructions=state.search_instructions,
        web_results="",
        file_name=None,
        index=None,
        index_name=state.index_name,
        index_folder_path=state.index_folder_path,
    )

async def research_node(state: GraphState) -> Command:
    research_agent = create_react_agent(
        llm, tools=[tavily_tool],
        prompt=("As an AI research specialist, your task is to scour the internet for pertinent information based on the user's specified search_instructions."
                " Avoid summarizing or organizing the content; simply gather raw, unprocessed information. Do not engage in follow-up questions or discussions, "
                "focus solely on compiling data as you find it online.")
    )
    result = await research_agent.ainvoke(
        {"messages": [HumanMessage(content=state.search_instructions)]}
    )
    web_results = result["messages"][-1].content
    return Command(
        update={
            "web_results": web_results,
        })

async def create_file_name(state: GraphState) -> Command:
    file_name = await llm.ainvoke(
        [SystemMessage(
            """
            You are a message summarizer.
            Generate a file name from the received message, replacing spaces with underscores,
            to create a succinct and descriptive identification.
            For instance, 'Need data about formula 1' should be converted to format like 'data_about_formula_1'.
            """
        ),
        state.search_instructions])

    return Command(
        update={
            "file_name": file_name.content,
        })


async def add_data_to_context_grounding_index(state: GraphState) -> MessagesState:
    current_timestamp = int(time.time())
    file_name = state.file_name
    await uipath.context_grounding.add_to_index_async(
        name=state.index_name,
        blob_file_path=f"{file_name}-{current_timestamp}.txt",
        content_type="application/txt",
        content=state.web_results,
        folder_path=state.index_folder_path,
    )
    return MessagesState(messages=[AIMessage("Relevant information uploaded to bucket.")])



# Build the state graph
builder = StateGraph(input=GraphInput, output=MessagesState)
builder.add_node("research", research_node)
builder.add_node("add_data_to_context_grounding_index", add_data_to_context_grounding_index)
builder.add_node("prepare_input", prepare_input)
builder.add_node("create_file_name", create_file_name)

builder.add_edge(START, "prepare_input")
builder.add_edge("prepare_input", "create_file_name")
builder.add_edge("create_file_name", "research")
builder.add_edge("research", "add_data_to_context_grounding_index")
builder.add_edge("add_data_to_context_grounding_index", END)

# Compile the graph
graph = builder.compile()
