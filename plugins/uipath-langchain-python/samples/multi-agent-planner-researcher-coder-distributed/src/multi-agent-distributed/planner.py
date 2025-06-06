from typing import List, Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.types import Command, interrupt
from pydantic import BaseModel, Field
from typing_extensions import TypedDict
from uipath.models import InvokeProcess

worker_agents = {"researcher": "researcher-agent", "coder": "coder-agent"}
agent_names = list(worker_agents.values())
options = agent_names + ["FINISH"]


class Router(TypedDict):
    """Worker to route to next. If no workers needed, route to FINISH."""

    next: Literal[*options]


class GraphInput(BaseModel):
    question: str


class GraphOutput(BaseModel):
    answer: str


class PlanStep(BaseModel):
    """A single step in the execution plan"""

    agent: str = Field(
        description="The agent to execute this step (researcher-agent or coder-agent)"
    )
    task: str = Field(description="The specific task for the agent to perform")


class ExecutionPlan(BaseModel):
    """A plan for executing a complex task using specialized agents"""

    steps: List[PlanStep] = Field(
        description="The ordered sequence of steps to execute"
    )


class State(MessagesState):
    """State for the graph"""

    next: str
    next_task: str
    execution_plan: ExecutionPlan = None
    current_step: int = 0


def input(state: GraphInput):
    return {
        "messages": [
            HumanMessage(content=state.question),
        ],
        "next": "",
        "next_task": "",
        "execution_plan": None,
        "current_step": 0,
    }


llm = ChatAnthropic(model="claude-3-5-sonnet-latest")


async def create_plan(state: State) -> Command:
    """Create an execution plan based on the user's question."""
    parser = PydanticOutputParser(pydantic_object=ExecutionPlan)

    planning_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a planning agent that creates execution plans for tasks.
        Break down complex tasks into steps that can be performed by specialized agents.""",
            ),
            ("human", "{question}"),
            (
                "system",
                """
        Based on the user's request, create a structured execution plan.

        {format_instructions}

        Available agents:
        - researcher-agent: Finds information, formulas, and reference material
        - coder-agent: Performs calculations and evaluates formulas with specific values

        Create a plan with the minimum necessary steps to complete the task.
        """,
            ),
        ]
    )
    # Format the prompt with parser instructions and the user question
    formatted_prompt = planning_prompt.format(
        question=state["messages"][0].content,
        format_instructions=parser.get_format_instructions(),
    )

    plan_response = await llm.ainvoke(formatted_prompt)

    try:
        plan_output = parser.parse(plan_response.content)

        steps = []
        for step in plan_output.steps:
            agent_key = "researcher" if "researcher" in step.agent else "coder"
            steps.append(
                PlanStep(agent=worker_agents[agent_key], task=step.task)
            )

        execution_plan = ExecutionPlan(steps=steps)
    except Exception as e:
        print(f"Failed to parse plan: {e}")
        return Command(goto="supervisor")

    # Create a plan summary for the messages
    plan_summary = "Execution Plan:\n" + "\n".join(
        [
            f"{i + 1}. {step.agent}: {step.task}"
            for i, step in enumerate(execution_plan.steps)
        ]
    )

    return Command(
        update={
            "messages": [
                HumanMessage(
                    content=f"I've created an execution plan for this task:\n{plan_summary}"
                )
            ],
            "execution_plan": execution_plan,
        },
        goto="supervisor",
    )


def supervisor_node(state: State) -> Command | GraphOutput:
    """Execute the next step in the plan or finish if complete."""
    plan = state["execution_plan"]

    # If no plan exists, create one
    if plan is None:
        return Command(goto="create_plan")

    # If we've completed all steps, finish
    if state["current_step"] >= len(plan.steps):
        return GraphOutput(answer=state["messages"][-1].content)

    # Get the next step from the plan
    next_step = plan.steps[state["current_step"]]
    next_agent = next_step.agent
    next_task = next_step.task

    # Return command to invoke the next agent
    return Command(goto="invoke_agent", update={"next": next_agent, "next_task": next_task})


def invoke_agent(state: State) -> Command:
    """Invoke the agent specified in the current step of the execution plan."""

    agent_name = state["next"]
    task = state["next_task"]

    # Create a list of messages to send to the agent
    # Keep previous agent messages + append the current task
    input_messages = [
        msg for msg in state["messages"]
        if isinstance(msg, HumanMessage) and hasattr(msg, "name") and msg.name
    ]
    input_messages.append(HumanMessage(content=task))

    agent_response = interrupt(
        InvokeProcess(
            name=state["next"], input_arguments={"messages": input_messages}
        )
    )

    response_content = agent_response["answer"]

    agent_message = HumanMessage(content=response_content, name=agent_name)

    return Command(
        update={
            "messages": [agent_message],
            "current_step": state["current_step"] + 1,
        },
        goto="supervisor",
    )


# Build the state graph
builder = StateGraph(State, input=GraphInput, output=GraphOutput)
builder.add_node("input", input)
builder.add_node("create_plan", create_plan)
builder.add_node("supervisor", supervisor_node)
builder.add_node("invoke_agent", invoke_agent)

builder.add_edge(START, "input")
builder.add_edge("input", "supervisor")
builder.add_edge("create_plan", "supervisor")
builder.add_edge("invoke_agent", "supervisor")


# Compile the graph
graph = builder.compile()
