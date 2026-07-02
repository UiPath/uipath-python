# Coded MCP on ACI — spike branch pointer

Branch **`spike/coded-mcp-aci-runtime`** is part of a **cross-repo spike/POC** that makes coded MCP
servers run as Azure Container Instances orchestrated by AgentHub (start faster / stay alive longer).

**This repo's slice:** the CLI `uipath image build` / `uipath image publish` commands
(`packages/uipath/src/uipath/_cli/cli_image.py`) — package a coded MCP project into a container
image and push it to ACR.

**Full handoff, docs, architecture, and how to resume on another machine** live in the
**`UiPath/AgentHubService`** repo on the **same branch**:
- `docs/coded-mcp-aci-HANDOFF.md` — **start here**
- `docs/coded-mcp-aci-poc-guide.md` — how it works + how to run
- `docs/coded-mcp-aci-road-to-production.md`, `docs/coded-mcp-aci-cost-analysis.md`

**Companion branches (same name `spike/coded-mcp-aci-runtime`):** `UiPath/AgentHubService`,
`UiPath/uipath-python`, `UiPath/uipath-mcp-python`.
