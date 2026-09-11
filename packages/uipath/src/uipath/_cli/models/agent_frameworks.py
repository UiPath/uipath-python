"""Agent frameworks supported by `uipath new --type agent`.

Each framework's integration package registers a middleware that claims
agent scaffolds for its framework.
"""

import importlib.metadata
from enum import StrEnum

from .project_types import ProjectType


class AgentFramework(StrEnum):
    """Agent frameworks with a UiPath integration package."""

    CLAUDE_SDK = "claude-sdk"
    GOOGLE_ADK = "google-adk"
    LANGCHAIN = "langchain"
    LLAMAINDEX = "llamaindex"
    MICROSOFT_AGENT_FRAMEWORK = "microsoft-agent-framework"
    OPENAI_AGENTS = "openai-agents"
    PYDANTIC_AI = "pydantic-ai"

    @property
    def package(self) -> str:
        """PyPI package that provides this framework's UiPath integration."""
        return _AGENT_FRAMEWORK_PACKAGES[self]

    def claims_scaffold(
        self,
        project_type: ProjectType,
        agent_framework: "AgentFramework | None",
    ) -> bool:
        """Whether this framework's `new` middleware should scaffold the project.

        Every integration answers the same question — `--type auto` (the
        default) lets the installed integration win over the base function
        scaffold, and `--type agent` belongs to the framework it names — so
        the gate lives here rather than being repeated in each integration:

            if not AgentFramework.LANGCHAIN.claims_scaffold(
                project_type, agent_framework
            ):
                return MiddlewareResult(should_continue=True)

        Comparisons are by value, not identity, so callers passing plain
        strings (an older base CLI, or a direct middleware call) still gate
        correctly.
        """
        return project_type == ProjectType.AUTO or (
            project_type == ProjectType.AGENT and agent_framework == self
        )


# uipath-langchain lives in its own repo; the rest come from
# UiPath/uipath-integrations-python (note: microsoft-agent-framework ships
# as `uipath-agent-framework`).
_AGENT_FRAMEWORK_PACKAGES = {
    AgentFramework.CLAUDE_SDK: "uipath-claude-sdk",
    AgentFramework.GOOGLE_ADK: "uipath-google-adk",
    AgentFramework.LANGCHAIN: "uipath-langchain",
    AgentFramework.LLAMAINDEX: "uipath-llamaindex",
    AgentFramework.MICROSOFT_AGENT_FRAMEWORK: "uipath-agent-framework",
    AgentFramework.OPENAI_AGENTS: "uipath-openai-agents",
    AgentFramework.PYDANTIC_AI: "uipath-pydantic-ai",
}


def installed_agent_frameworks() -> list[AgentFramework]:
    """Agent frameworks whose integration package is installed in this environment."""
    installed = []
    for framework in AgentFramework:
        try:
            importlib.metadata.distribution(framework.package)
        except importlib.metadata.PackageNotFoundError:
            continue
        installed.append(framework)
    return installed
