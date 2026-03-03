# Automation Suite

## Airgapped Deployments

Airgapped Automation Suite environments (deployments without internet access) require special configuration for Python package dependencies. You need to configure your project to use a Python package feed that is accessible within your environment.

You have two main options for managing Python packages:

1. **Use Azure DevOps Artifacts** - Leverage Azure DevOps as a Python package feed with upstream PyPI sources (suitable for environments with restricted but not fully airgapped access)
2. **Host your own Python package index** - Set up a self-hosted PyPI mirror or repository within your infrastructure (required for truly airgapped environments)

### Using Azure DevOps Artifacts as a Python Feed

Azure DevOps Artifacts can serve as a private Python package feed that includes packages from common public sources (PyPI). This is suitable for environments with restricted internet access where Azure DevOps services are still accessible.

#### Step 1: Create an Azure DevOps Artifacts Feed

1. Navigate to your Azure DevOps project
2. Go to **Artifacts**
3. Click **Create Feed**
4. Configure your feed settings and ensure you select the option to **Include packages from common public sources** (this will upstream PyPI packages)

#### Step 2: Authenticate with a Personal Access Token (PAT)

You'll need to create a Personal Access Token (PAT) to authenticate with your Azure DevOps feed.

1. Follow the [Microsoft documentation to create a PAT](https://learn.microsoft.com/en-us/azure/devops/organizations/accounts/use-personal-access-tokens-to-authenticate?view=azure-devops&tabs=Windows)
2. Ensure your PAT has at least **Packaging (Read)** permissions
3. Save your PAT securely - you'll need it for the next step

#### Step 3: Configure Your Project

Add the following configuration to your `pyproject.toml` file:

```toml
[[tool.uv.index]]
name = "my-feed"
url = "https://az:PAT_STRING@YOUR_ORG.pkgs.visualstudio.com/YourProject/_packaging/my-feed/pypi/simple/"
publish-url = "https://az:PAT_STRING@YOUR_ORG.pkgs.visualstudio.com/YourProject/_packaging/my-feed/pypi/upload/"
default = true
```

Replace the following placeholders:

- **`PAT_STRING`**: Your actual Personal Access Token from Step 2
- **`YOUR_ORG`**: Your Azure DevOps organization name
- **`YourProject`**: Your Azure DevOps project name
- **`my-feed`**: The name of your feed (in both the `name` field and the URL)

/// tip
**Organization-scoped feeds**: If you're using an organization-scoped feed instead of a project-scoped feed, the URL format will be slightly different, but the same authentication logic applies. The URL will follow this pattern:

```toml
url = "https://az:PAT_STRING@YOUR_ORG.pkgs.visualstudio.com/_packaging/my-feed/pypi/simple/"
```

Note the absence of the project name in the URL path.
///

/// tip
**Using environment variables**: You can also configure the feed URL using environment variables instead of hardcoding the PAT in `pyproject.toml`:

```toml
[[tool.uv.index]]
name = "my-feed"
url = "https://az:${AZURE_DEVOPS_PAT}@YOUR_ORG.pkgs.visualstudio.com/YourProject/_packaging/my-feed/pypi/simple/"
default = true # to use this feed as your default
```

Then set the environment variable before running your commands locally:

```bash
export AZURE_DEVOPS_PAT=your_pat_token
```

**Important**: When deploying your process to UiPath, you'll need to configure these environment variables in the process settings. Navigate to your process in UiPath Orchestrator and add the environment variables (e.g., `AZURE_DEVOPS_PAT`) with their corresponding values. This ensures your process can authenticate with the external feed when running in the UiPath environment.
///

/// tip
**Specifying sources for specific packages**: If you don't want to set your custom feed as the default, you can use `[tool.uv.sources]` to specify which packages should come from your custom feed:

```toml
[[tool.uv.index]]
name = "my-feed"
url = "https://az:PAT_STRING@YOUR_ORG.pkgs.visualstudio.com/YourProject/_packaging/my-feed/pypi/simple/"

[tool.uv.sources]
uipath = { index = "my-feed" }
# Add other packages as needed
some-private-package = { index = "my-feed" }
```

This allows you to selectively pull specific packages from your custom feed while using the default PyPI for others.
///

#### Step 4: Install Dependencies

Once configured, you can install dependencies using `uv`:

<!-- termynal -->
```bash
> uv add uipath
⠋ Resolved 25 packages from my-feed
✓  Successfully installed uipath
```

#### Verification

To verify your feed configuration is working correctly, you can check that `uv` resolves packages from your custom feed:

<!-- termynal -->
```bash
> uv add --dry-run uipath
⠋ Checking package availability...
✓  All packages available from my-feed
```

### Hosting Your Own Python Package Index

For truly airgapped deployments where you need complete control over your infrastructure, you can host your own Python package index within your network. This approach eliminates any external dependencies and provides full control over the packages available in your environment.

#### Popular Self-Hosted Solutions

Several tools are available for hosting a Python package index:

- **[devpi](https://devpi.net/)** - A PyPI-compatible server with caching and mirroring capabilities
- **[PyPI Server](https://pypi.org/project/pypiserver/)** - A minimal PyPI-compatible server for hosting packages
- **[JFrog Artifactory](https://jfrog.com/artifactory/)** - Enterprise artifact repository with Python support
- **[Sonatype Nexus Repository](https://www.sonatype.com/products/nexus-repository)** - Universal artifact repository manager
- **[bandersnatch](https://github.com/pypa/bandersnatch)** - PyPI mirror client for creating a complete or filtered mirror

#### Configuration for Self-Hosted Index

Once you have your Python package index set up and accessible within your airgapped network, configure your `pyproject.toml` to point to it:

```toml
[[tool.uv.index]]
name = "internal-pypi"
url = "https://pypi.internal.company.com/simple/"
default = true
```

If your internal index requires authentication:

```toml
[[tool.uv.index]]
name = "internal-pypi"
url = "https://username:password@pypi.internal.company.com/simple/"
default = true
```
