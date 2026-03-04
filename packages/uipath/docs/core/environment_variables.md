# Environment Variables

Environment variables are configuration values stored at the operating system level that can be accessed by applications and scripts. They provide a flexible way to configure application behavior without hardcoding values in your source code.

Environment variables are loaded in the following order (highest to lowest priority):

1. `.env` file in the current directory
2. System environment variables
3. Default values in code

Example:
```bash
# .env file
UIPATH_FOLDER_PATH=/default/path

# System environment
export UIPATH_FOLDER_PATH=/system/path
```
/// warning
When deploying your agent to production, ensure that all required environment variables (such as API keys and custom configurations) are properly configured in your process settings. This step is crucial for the successful operation of your published package.
///

## Design

Create a `.env` file in your project's root directory to manage environment variables locally. When using the `uipath auth` or `uipath new my-agent` commands, this file is automatically created.

The `uipath auth` command automatically populates this file with essential variables:

- `UIPATH_URL`: Your UiPath Orchestrator instance URL
- `UIPATH_ACCESS_TOKEN`: Authentication token for API access

### Folder Configuration
Most UiPath services operate within a specific folder context. Configure your folder context using either:

- `UIPATH_FOLDER_PATH`: The full path to your target folder
- `UIPATH_FOLDER_KEY`: The unique identifier for your target folder

To obtain the folder path, right-click on the folder in UiPath Orchestrator and select "Copy folder path" from the context menu.

<picture data-light="../assets/copy_path_light.png" data-dark="../assets/copy_path_dark.png">
  <source
    media="(prefers-color-scheme: dark)"
    srcset="
      ../assets/copy_path_dark.png
    "
  />
  <img
    src="../assets/copy_path_light.png"
  />
</picture>

### Telemetry
To help us improve the developer experience, the CLI collects basic usage data about command invocations. For more details about UiPath's privacy practices, please review the [privacy statement](https://www.uipath.com/legal/privacy-policy).

Telemetry is enabled by default. You can opt out by setting the `UIPATH_TELEMETRY_ENABLED` environment variable to `false` in your `.env` file:

```bash
UIPATH_TELEMETRY_ENABLED=false
```

## Runtime

When executing processes or starting jobs, you can configure environment variables through the UiPath Orchestrator interface. For sensitive information like API keys and secrets, we strongly recommend using secret assets instead of environment variables. Secret assets provide enhanced security and better management capabilities.

### Secret Assets
To use a secret asset in your environment variables, reference it using the following format:

```bash
NAME=%ASSETS/your-secret-asset-name%
```

<picture data-light="../assets/cloud_env_var_light.gif" data-dark="../assets/cloud_env_var_dark.gif">
  <source
    media="(prefers-color-scheme: dark)"
    srcset="
      ../assets/cloud_env_var_dark.gif
    "
  />
  <img
    src="../assets/cloud_env_var_light.gif"
  />
</picture>

### Sensitive Variables
If you must use environment variables for sensitive information (not recommended), variables containing `API_KEY` or `SECRET` in their names will have their values masked as `****` in the interface for security purposes.

<picture data-light="../assets/cloud_env_var_secret_light.png" data-dark="../assets/cloud_env_var_secret_dark.png">
  <source
    media="(prefers-color-scheme: dark)"
    srcset="
      ../assets/cloud_env_var_secret_dark.png
    "
  />
  <img
    src="../assets/cloud_env_var_secret_light.png"
  />
</picture>

### Log Level
The `LOG_LEVEL` environment variable controls the verbosity of logging in the Orchestrator UI's Log tab during runtime execution. This setting determines which log messages are displayed in the interface.

| Level | Description |
|-------|-------------|
| TRACE | Most detailed logging level, shows all possible information |
| DEBUG | Detailed information for debugging purposes |
| INFORMATION | General operational information |
| WARNING | Warning messages for potentially harmful situations |
| ERROR | Error events that might still allow the application to continue |
| CRITICAL | Critical events that may lead to application failure |
| NONE | No logging |

The default value is `INFORMATION`

### Builtin Variables
The runtime environment automatically includes certain variables (such as `UIPATH_FOLDER_KEY`, `UIPATH_ROBOT_KEY`), eliminating the need for manual configuration.