from uipath import UiPath
from uipath.models.mcp import McpServer
from uipath.tracing import traced

uipath = UiPath()


def list_mcp_servers() -> list[McpServer]:
    """Retrieve MCP servers from UiPath.

    Returns:
        list[McpServer]: A list of MCP server configurations.
    """
    return uipath.mcp.list(folder_path="Shared")


def retrieve_mcp_server(slug: str) -> McpServer:
    """Retrieve a specific MCP server by slug.

    Args:
        slug (str): The server slug identifier.

    Returns:
        McpServer: The MCP server configuration.
    """
    return uipath.mcp.retrieve(slug, folder_path="Shared")


def format_servers(servers: list[McpServer], detailed_server: McpServer | None = None) -> str:
    """Format the list of MCP servers for display.

    Args:
        servers (list[McpServer]): The list of MCP servers.
        detailed_server (McpServer | None): Detailed information about a specific server.

    Returns:
        str: Formatted string with server information.
    """
    if not servers:
        return "No MCP servers found in the specified folder."

    result_lines = [f"Found {len(servers)} MCP server(s):\n"]

    for idx, server in enumerate(servers, 1):
        server_name = server.name
        server_slug = server.slug
        server_type = server.type
        server_status = server.status

        result_lines.append(f"{idx}. {server_name}")
        result_lines.append(f"   Slug: {server_slug}")
        result_lines.append(f"   Type: {server_type}")
        result_lines.append(f"   Status: {server_status}")

        result_lines.append("")

    if detailed_server:
        result_lines.append("\n--- Detailed Information for First Server ---\n")
        result_lines.append(f"Name: {detailed_server.name}")
        result_lines.append(f"Slug: {detailed_server.slug}")
        result_lines.append(f"ID: {detailed_server.id}")
        result_lines.append(f"Type: {detailed_server.type}")
        result_lines.append(f"Status: {detailed_server.status}")
        result_lines.append(f"Version: {detailed_server.version}")
        result_lines.append(f"Is Active: {detailed_server.is_active}")

        if detailed_server.description:
            result_lines.append(f"Description: {detailed_server.description}")

        if detailed_server.created_at:
            result_lines.append(f"Created At: {detailed_server.created_at}")

        if detailed_server.updated_at:
            result_lines.append(f"Updated At: {detailed_server.updated_at}")

        if detailed_server.type == "Command":
            result_lines.append(f"Command: {detailed_server.command}")
            result_lines.append(f"Arguments: {detailed_server.arguments}")

        if detailed_server.runtimes_count is not None:
            result_lines.append(f"Runtimes Count: {detailed_server.runtimes_count}")

    return "\n".join(result_lines).strip()


@traced()
def main() -> str:
    """Main entry point for the agent.

    Returns:
        str: Formatted list of MCP servers with detailed info about the first one.
    """
    servers = list_mcp_servers()

    detailed_server = None
    if servers:
        first_server_slug = servers[0].slug
        if first_server_slug:
            detailed_server = retrieve_mcp_server(first_server_slug)

    return format_servers(servers, detailed_server)
