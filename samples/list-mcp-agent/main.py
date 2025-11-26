import os

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from pydantic.dataclasses import dataclass

from uipath.platform import UiPath
from uipath.platform.orchestrator import McpServer
from uipath.tracing import traced


@dataclass
class McpAgentInput:
    server_name: str


@dataclass
class McpAgentOutput:
    message: str


def list_mcp_servers() -> list[McpServer]:
    uipath = UiPath()
    return uipath.mcp.list(folder_path="Shared")


def retrieve_mcp_server(slug: str) -> McpServer:
    uipath = UiPath()
    return uipath.mcp.retrieve(slug, folder_path="Shared")


async def connect_and_list_tools(server: McpServer) -> list[str]:
    tool_descriptions = []

    try:
        access_token = os.environ.get("UIPATH_ACCESS_TOKEN")
        if not access_token:
            tool_descriptions.append("No UIPATH_ACCESS_TOKEN environment variable found. Please authenticate using `uipath auth`")
            return tool_descriptions

        if not server.mcp_url:
            tool_descriptions.append("No MCP URL available for this server")
            return tool_descriptions

        headers = {"Authorization": f"Bearer {access_token}"}

        async with streamablehttp_client(
            url=server.mcp_url,
            headers=headers,
            timeout=60,
            sse_read_timeout=60,
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()

                if not tools_result.tools:
                    tool_descriptions.append("No tools available")
                else:
                    for tool in tools_result.tools:
                        tool_descriptions.append(
                            f"  - {tool.name}: {tool.description or 'No description'}"
                        )

    except Exception as e:
        tool_descriptions.append(f"Error connecting to server: {str(e)}")

    return tool_descriptions


def format_servers_with_tools(
    detailed_server: McpServer | None = None,
    tools: list[str] | None = None,
) -> str:
    result_lines = [f"Available Tools for {detailed_server.name if detailed_server else 'Unknown Server'}\n"]
    if tools:
        result_lines.extend(tools)

    return "\n".join(result_lines).strip()


def format_server_not_found(servers: list[McpServer], requested_name: str) -> str:
    result_lines = [
        f"Server '{requested_name}' Not Found\n",
        "The requested MCP server does not exist.\n",
        "Available MCP servers:",
    ]

    if servers:
        for server in servers:
            status = "active" if server.is_active else "inactive"
            server_type = server.type if server.type is not None else "unknown"
            result_lines.append(f"  - {server.name} (slug: {server.slug}, status: {status}, type: {server_type})")
    else:
        result_lines.append("No servers available")

    return "\n".join(result_lines)


@traced()
async def main(input: McpAgentInput) -> McpAgentOutput:
    servers = list_mcp_servers()

    target_server = next((s for s in servers if s.name == input.server_name), None)

    if not target_server:
        message = format_server_not_found(servers, input.server_name)
        return McpAgentOutput(message=message)

    detailed_server = retrieve_mcp_server(target_server.slug)
    tools = await connect_and_list_tools(detailed_server)

    message = format_servers_with_tools(detailed_server=detailed_server, tools=tools)
    return McpAgentOutput(message=message)
