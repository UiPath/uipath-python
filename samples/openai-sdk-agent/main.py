import asyncio
from collections import Counter

import dotenv
from agents import (
    Agent,
    AgentToolStreamEvent,
    ModelSettings,
    Runner,
    function_tool,
    trace,
)
from pydantic import BaseModel

from uipath.platform import UiPath
from uipath.tracing import traced

dotenv.load_dotenv()


class InputModel(BaseModel):
    query: str | None = None


class OutputModel(BaseModel):
    result: str


class JobStatistics(BaseModel):
    """Statistics for jobs."""

    running: int
    pending: int
    successful: int
    faulted: int
    stopped: int
    total: int
    process_name: str | None = None
    state: str | None = None


class JobDetails(BaseModel):
    """Detailed information about a job."""

    id: int
    key: str
    process: str | None
    state: str
    robot: str | None
    start_time: str | None
    end_time: str | None
    creation_time: str
    info: str | None = None
    source: str | None = None


@traced(name="get_uipath_client")
def get_uipath_client() -> UiPath:
    """Initialize and return a UiPath client.

    The client automatically resolves from environment variables:
    - UIPATH_URL: Base URL for UiPath Orchestrator
    - UIPATH_ACCESS_TOKEN: Access token for authentication

    Returns:
        UiPath: An instance of the UiPath client.
    """
    return UiPath()


@function_tool(
    name_override="get_job_statistics",
    description_override="Get statistics and counts for UiPath Orchestrator jobs, optionally filtered by process name and/or state.",
)
def get_job_statistics(
    process_name: str | None = None, state: str | None = None
) -> JobStatistics:
    """Get statistics for jobs from Orchestrator.

    Args:
        process_name: Optional process name to filter jobs by (uses Release/Name filter)
        state: Optional state to filter jobs by (e.g., 'Running', 'Successful', 'Faulted')

    Returns:
        JobStatistics object with counts for each job state
    """
    client = get_uipath_client()

    # Build OData filter
    filters = []
    if process_name:
        filters.append(f"Release/Name eq '{process_name}'")
    if state:
        filters.append(f"State eq '{state}'")

    filter_str = " and ".join(filters) if filters else None

    # List jobs with ordering by creation time (most recent first)
    result = client.jobs.list(
        filter=filter_str,
        orderby="CreationTime desc",
        top=1000,
    )
    jobs = [job.model_dump() for job in result.items]

    # Calculate statistics by status (single pass through jobs)
    state_counts = Counter(job.get("state") for job in jobs)

    return JobStatistics(
        running=state_counts.get("Running", 0),
        pending=state_counts.get("Pending", 0),
        successful=state_counts.get("Successful", 0),
        faulted=state_counts.get("Faulted", 0),
        stopped=state_counts.get("Stopped", 0),
        total=len(jobs),
        process_name=process_name,
        state=state,
    )


@function_tool(
    name_override="get_latest_job_details",
    description_override="Get detailed information about the most recent job for a specific process, optionally filtered by state.",
)
def get_latest_job_details(process_name: str, state: str | None = None) -> JobDetails:
    """Get the latest job details for a specific process.

    Args:
        process_name: Name of the process (uses Release/Name filter)
        state: Optional state filter (e.g., 'Running', 'Successful', 'Faulted')

    Returns:
        JobDetails object with detailed job information

    Raises:
        ValueError: If no jobs found for the given process/state
    """
    client = get_uipath_client()

    # Build OData filter with Release/Name
    filters = [f"Release/Name eq '{process_name}'"]
    if state:
        filters.append(f"State eq '{state}'")

    filter_str = " and ".join(filters)

    result = client.jobs.list(
        filter=filter_str,
        orderby="CreationTime desc",
        top=1,
    )

    if not result.items:
        error_msg = f"No jobs found for process '{process_name}'"
        if state:
            error_msg += f" with state '{state}'"
        raise ValueError(error_msg)

    job = result.items[0].model_dump()

    # Extract robot name
    robot_name = job.get("robot", {}).get("name") if job.get("robot") else None

    # Extract process name from release
    process_name_from_job = (
        job.get("release", {}).get("name") if job.get("release") else None
    )

    return JobDetails(
        id=job.get("id"),
        key=job.get("key"),
        process=process_name_from_job,
        state=job.get("state"),
        robot=robot_name,
        start_time=job.get("start_time"),
        end_time=job.get("end_time"),
        creation_time=job.get("creation_time"),
        info=job.get("info"),
        source=job.get("source"),
    )


def handle_stream(event: AgentToolStreamEvent) -> None:
    """Print streaming events emitted by the nested job agent."""
    stream = event["event"]

    # Filter out noisy internal events
    if stream.type in ["raw_response_event", "raw_request_event"]:
        return

    agent_name = event["agent"].name

    # Handle run_item_stream_event to extract tool call details
    if stream.type == "run_item_stream_event" and hasattr(stream, "item"):
        item = stream.item
        item_type = type(item).__name__

        if item_type == "ToolCallItem":
            # Tool is being called
            raw_item = item.raw_item
            print(f"\n🔧 [{agent_name}] Tool Call Started: {raw_item.name}")

            if raw_item.arguments:
                import json

                try:
                    args = json.loads(raw_item.arguments)
                    print("   └─ Arguments:")
                    for key, value in args.items():
                        print(f"      • {key}: {value}")
                except:
                    print(f"   └─ Arguments: {raw_item.arguments}")

        elif item_type == "ToolCallOutputItem":
            # Tool call completed
            print(f"\n✓ [{agent_name}] Tool Call Completed")

            if hasattr(item, "output"):
                print(f"   └─ Result: {item.output}")

        elif item_type == "MessageOutputItem":
            # Agent generated a message
            if hasattr(item, "raw_item") and hasattr(item.raw_item, "content"):
                for content in item.raw_item.content:
                    if hasattr(content, "text"):
                        print(f"\n💬 [{agent_name}] Message:\n{content.text}")

        return

    # Handle other event types (if any)
    if stream.type == "error":
        print(f"❌ [{agent_name}] Error: {stream}")


@traced(name="UiPath Job Monitoring Agent Main")
async def main(input_model: InputModel) -> OutputModel:
    """Main function to run the UiPath Job Monitoring Agent.

    Args:
        input_model: Input model with a query for the agent.

    Returns:
        OutputModel: Result containing the agent's response.
    """
    # Use input query or default
    user_query = input_model.query or "Can you check the status of all jobs?"

    # Use OpenAI API (reads from OPENAI_API_KEY environment variable)
    print("Using OpenAI API for AI models...")
    model_name = "gpt-5.2"

    with trace("UiPath Job Monitoring Agent"):
        job_agent = Agent(
            name="Job Management Agent",
            instructions=(
                "You are a UiPath job management agent that monitors and reports on Orchestrator jobs. "
                "Use 'get_job_statistics' to get counts and statistics of jobs (optionally filtered by process name and/or state). "
                "Use 'get_latest_job_details' to get detailed information about the most recent job for a specific process. "
                "Extract the process name and optionally the state from the user's query and use the appropriate tool."
            ),
            model_settings=ModelSettings(tool_choice="required"),
            tools=[get_job_statistics, get_latest_job_details],
            model=model_name,
        )

        job_agent_tool = job_agent.as_tool(
            tool_name="job_agent",
            tool_description="Agent that handles UiPath Orchestrator job queries and monitoring.",
            on_stream=handle_stream,
        )

        main_agent = Agent(
            name="UiPath Operations Agent",
            instructions=(
                "You are a UiPath operations agent. Always call the job management agent to answer "
                "questions about jobs and job status, and return the response to the user."
            ),
            tools=[job_agent_tool],
            model=model_name,
        )

        result = await Runner.run(
            main_agent,
            user_query,
        )

    print(f"\nFinal response:\n{result.final_output}")
    return OutputModel(result=result.final_output)


if __name__ == "__main__":
    # Example usage with different queries:
    # 1. Check all jobs status
    # asyncio.run(main(InputModel(query="What is the status of all jobs?")))

    # 2. Check jobs by process name
    # asyncio.run(main(InputModel(query="Show me the status of 'InvoiceProcessing' jobs")))

    # 3. Get latest job details for a process
    # asyncio.run(main(InputModel(query="Show me details for the latest 'InvoiceProcessing' job")))

    # 4. Check jobs by process and state
    # asyncio.run(main(InputModel(query="Show me running jobs for 'InvoiceProcessing'")))

    # 5. Use default query
    asyncio.run(main(InputModel(query="What is the status of all jobs?")))
