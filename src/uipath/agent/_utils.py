from pathlib import PurePath

from httpx import Response

from uipath._cli._utils._studio_project import (
    ProjectFile,
    ProjectFolder,
    StudioClient,
    resolve_path,
)
from uipath.agent.models.agent import (
    AgentToolDefinition,
    BaseToolDefinition,
    EscalationToolDefinition,
    IntegrationToolDefinition,
    LowCodeAgentDefinition,
)


async def get_file(
    folder: ProjectFolder, path: PurePath, studio_client: StudioClient
) -> Response:
    resolved = resolve_path(folder, path)
    assert isinstance(resolved, ProjectFile), "Path file not found."
    return await studio_client.download_file_async(resolved.id)


async def load_lowcode_agent_definition(project_id: str):
    studio_client = StudioClient(project_id=project_id)
    project_structure = await studio_client.get_project_structure_async()

    agent = (
        await get_file(project_structure, PurePath("agent.json"), studio_client)
    ).json()
    assert agent["type"] == "lowCode", "Solution must be a low code agent."
    agent_name = project_structure.name  # TODO how do I get name?
    input_schema = agent["inputSchema"]
    output_schema = agent["outputSchema"]
    system_prompt, user_prompt = agent["messages"]

    folder = resolve_path(project_structure, PurePath("resources"))
    assert isinstance(folder, ProjectFolder), "Path file not found."
    resources = folder.folders
    tools = []
    for resource in resources:
        resource_definition = (
            await get_file(resource, PurePath("resource.json"), studio_client)
        ).json()
        resource_type = resource_definition["$resourceType"]
        tool_cls: type[BaseToolDefinition]
        if resource_type == "escalation":
            tool_cls = EscalationToolDefinition
            properties = {
                "type": resource_definition["escalationType"],
                "channels": resource_definition["channels"],
            }
            # properties = {""resource_definition["properties"]
            resource_input_schema = resource_definition["channels"][0]["inputSchema"]
            resource_output_schema = resource_definition["channels"][0]["outputSchema"]
        else:
            properties = resource_definition.get("properties", {})
            resource_input_schema = resource_definition["inputSchema"]
            if resource_definition["type"] == "integration":
                tool_cls = IntegrationToolDefinition
                resource_output_schema = {}
            else:
                tool_cls = AgentToolDefinition
                resource_output_schema = resource_definition["outputSchema"]
        tools.append(
            tool_cls(
                resource_type=resource_type,
                name=resource_definition["name"],
                description=resource_definition["description"],
                input_schema=resource_input_schema,
                output_schema=resource_output_schema,
                properties=properties,  # type: ignore[arg-type]
            )
        )
    return LowCodeAgentDefinition(
        name=agent_name,
        input_schema=input_schema,
        output_schema=output_schema,
        tools=tools,
        system_prompt=system_prompt["content"],
        user_prompt=user_prompt["content"],
    )
