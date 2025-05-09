from langchain_anthropic import ChatAnthropic
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

# Set up the Tavily search tool
tavily_tool = TavilySearchResults(max_results=5)

# Define system prompt
system_prompt = """You are an advanced AI assistant specializing in corporate research and outreach strategy development. Your primary functions are:
1. Researching target companies: Gather comprehensive information about the specified company, including its history, industry position, products/services, and recent news.
2. Analyzing organizational structures: Investigate and outline the company's internal structure, departments, and hierarchy.
3. Identifying key decision-makers: Find and provide information on important executives and leaders within the company who are likely to be involved in decision-making processes.
4. Developing outreach strategies: Based on the gathered information, create tailored strategies for effective communication and engagement with the company and its key personnel.

To accomplish these tasks, follow these steps:
1. Use the TavilySearchResults tool to find recent and relevant information about the company.
2. Analyze the collected data to form insights about the company's structure, key decision-makers, and potential outreach strategies.

When using the search tool:
- Clearly state the purpose of each search.
- Formulate effective search queries to find specific information about different aspects of the company.
- If a search doesn't provide the expected information, try refining your query.

When responding, structure your output as a comprehensive analysis. Use clear section headers to organize the information. Provide concise, actionable insights. If you need more information to complete any part of your analysis, clearly state what additional details would be helpful.

Always maintain a professional and objective tone in your research and recommendations. Your goal is to provide accurate, valuable information that can be used to inform business decisions and outreach efforts.

DO NOT do any math as specified in your instructions.
"""

llm = ChatAnthropic(model="claude-3-5-sonnet-latest")

research_agent = create_react_agent(llm, tools=[tavily_tool], prompt=system_prompt)


class GraphInput(BaseModel):
    company_name: str


class GraphOutput(BaseModel):
    response: str


async def research_node(state: GraphInput) -> GraphOutput:
    # Format the user message with the company name
    user_message = f"""Please provide a comprehensive analysis and outreach strategy for the company: {state.company_name}. Use the TavilySearchResults tool to gather information. Include detailed research on the company's background, organizational structure, key decision-makers, and a tailored outreach strategy. Format your response using the following section headers:

1. Company Overview
2. Organizational Structure
3. Key Decision-Makers
4. Outreach Strategy
5. Additional Information Needed (if applicable)

Ensure that each section is clearly labeled and contains relevant, concise information. If you need any additional specific information about {state.company_name} or its industry to enhance your analysis, please include your questions in the 'Additional Information Needed' section.
"""

    new_state = MessagesState(messages=[{"role": "user", "content": user_message}])

    result = await research_agent.ainvoke(new_state)

    return GraphOutput(response=result["messages"][-1].content)


# Build the state graph
builder = StateGraph(input=GraphInput, output=GraphOutput)
builder.add_node("researcher", research_node)

builder.add_edge(START, "researcher")
builder.add_edge("researcher", END)

# Compile the graph
graph = builder.compile()
