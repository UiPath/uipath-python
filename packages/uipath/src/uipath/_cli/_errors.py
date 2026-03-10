class EntrypointDiscoveryException(Exception):
    """Raised when entrypoint auto-discovery fails."""

    def __init__(self, entrypoints: list[str]):
        self.entrypoints = entrypoints

    def get_usage_help(self) -> list[str]:
        if self.entrypoints:
            lines = ["Available entrypoints:"]
            for name in self.entrypoints:
                lines.append(f"  - {name}")
            return lines
        return [
            "No entrypoints found.",
            "",
            "To configure entrypoints, use one of the following:",
            "  1. Functions project (uipath.json)",
            "  2. Framework-specific project (e.g. langgraph.json, llamaindex.json, openai_agents.json)",
            "  3. MCP project (mcp.json)",
        ]
