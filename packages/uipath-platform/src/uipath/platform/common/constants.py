"""Constants."""

# Environment variables
DOTENV_FILE = ".env"
ENV_BASE_URL = "UIPATH_URL"
ENV_EVAL_BACKEND_URL = "UIPATH_EVAL_BACKEND_URL"
ENV_UNATTENDED_USER_ACCESS_TOKEN = "UNATTENDED_USER_ACCESS_TOKEN"
ENV_UIPATH_ACCESS_TOKEN = "UIPATH_ACCESS_TOKEN"
ENV_FOLDER_KEY = "UIPATH_FOLDER_KEY"
ENV_FOLDER_PATH = "UIPATH_FOLDER_PATH"
ENV_JOB_KEY = "UIPATH_JOB_KEY"
ENV_JOB_ID = "UIPATH_JOB_ID"
ENV_ROBOT_KEY = "UIPATH_ROBOT_KEY"
ENV_TENANT_ID = "UIPATH_TENANT_ID"
ENV_TENANT_NAME = "UIPATH_TENANT_NAME"
ENV_ORGANIZATION_ID = "UIPATH_ORGANIZATION_ID"
ENV_TELEMETRY_ENABLED = "UIPATH_TELEMETRY_ENABLED"
ENV_TRACING_ENABLED = "UIPATH_TRACING_ENABLED"
ENV_UIPATH_PROJECT_ID = "UIPATH_PROJECT_ID"
# The cloud project the worker fetches package files from. For cloud projects this
# equals the agent ID; for local-workspace runs it is the debug project ID returned
# by prepareForCustomDebug. Falls back to UIPATH_PROJECT_ID for backwards compat.
ENV_UIPATH_FILE_SOURCE_PROJECT_ID = "UIPATH_FILE_SOURCE_PROJECT_ID"
# The logical agent the user authored. For local-workspace runs this differs from
# UIPATH_FILE_SOURCE_PROJECT_ID (which is the cloud debug project's GUID). When
# present, eval-side telemetry tags AgentId with this value instead of the file
# source. Routing of API callbacks (eval-run create) still uses the file source
# project so the URL points at a project the backend can resolve.
ENV_UIPATH_AGENT_ID = "UIPATH_AGENT_ID"
# The user who triggered the job. Set by the backend when it dispatches a worker
# under a service-account context, so the SDK can tag telemetry with the real user
# rather than the service account from the JWT.
ENV_UIPATH_CLOUD_USER_ID = "UIPATH_CLOUD_USER_ID"
# "Local" or "Cloud" — the source of the project files the worker is using.
ENV_UIPATH_PROJECT_FILES_SOURCE = "UIPATH_PROJECT_FILES_SOURCE"
ENV_PROJECT_KEY = "PROJECT_KEY"
ENV_PROCESS_KEY = "UIPATH_PROCESS_KEY"
ENV_UIPATH_PROCESS_UUID = "UIPATH_PROCESS_UUID"
ENV_UIPATH_TRACE_ID = "UIPATH_TRACE_ID"
ENV_UIPATH_PROCESS_VERSION = "UIPATH_PROCESS_VERSION"
ENV_UIPATH_CONFIG_PATH = "UIPATH_CONFIG_PATH"

# Headers
HEADER_FOLDER_KEY = "x-uipath-folderkey"
HEADER_FOLDER_PATH = "x-uipath-folderpath"
HEADER_FOLDER_PATH_ENCODED = "x-uipath-folderpath-encoded"
HEADER_USER_AGENT = "x-uipath-user-agent"
HEADER_TENANT_ID = "x-uipath-tenantid"
HEADER_INTERNAL_TENANT_ID = "x-uipath-internal-tenantid"
HEADER_INTERNAL_ACCOUNT_ID = "x-uipath-internal-accountid"
HEADER_JOB_KEY = "x-uipath-jobkey"
HEADER_PROCESS_KEY = "x-uipath-processkey"
HEADER_TRACE_ID = "x-uipath-traceid"
HEADER_AGENTHUB_CONFIG = "x-uipath-agenthub-config"
HEADER_LLMGATEWAY_BYO_CONNECTION_ID = "x-uipath-llmgateway-byoisconnectionid"
HEADER_SW_LOCK_KEY = "x-uipath-sw-lockkey"
HEADER_LICENSING_CONTEXT = "x-uipath-licensing-context"

# Data sources (request types)
ORCHESTRATOR_STORAGE_BUCKET_DATA_SOURCE_REQUEST = (
    "#UiPath.Vdbs.Domain.Api.V20Models.StorageBucketDataSourceRequest"
)
CONFLUENCE_DATA_SOURCE_REQUEST = (
    "#UiPath.Vdbs.Domain.Api.V20Models.ConfluenceDataSourceRequest"
)
DROPBOX_DATA_SOURCE_REQUEST = (
    "#UiPath.Vdbs.Domain.Api.V20Models.DropboxDataSourceRequest"
)
GOOGLE_DRIVE_DATA_SOURCE_REQUEST = (
    "#UiPath.Vdbs.Domain.Api.V20Models.GoogleDriveDataSourceRequest"
)
ONEDRIVE_DATA_SOURCE_REQUEST = (
    "#UiPath.Vdbs.Domain.Api.V20Models.OneDriveDataSourceRequest"
)

# Data sources
ORCHESTRATOR_STORAGE_BUCKET_DATA_SOURCE = (
    "#UiPath.Vdbs.Domain.Api.V20Models.StorageBucketDataSource"
)
CONFLUENCE_DATA_SOURCE = "#UiPath.Vdbs.Domain.Api.V20Models.ConfluenceDataSource"
DROPBOX_DATA_SOURCE = "#UiPath.Vdbs.Domain.Api.V20Models.DropboxDataSource"
GOOGLE_DRIVE_DATA_SOURCE = "#UiPath.Vdbs.Domain.Api.V20Models.GoogleDriveDataSource"
ONEDRIVE_DATA_SOURCE = "#UiPath.Vdbs.Domain.Api.V20Models.OneDriveDataSource"


# Local storage
TEMP_ATTACHMENTS_FOLDER = "uipath_attachments"

# LLM models
COMMUNITY_agents_SUFFIX = "-community-agents"

# File names
PYTHON_CONFIGURATION_FILE = "pyproject.toml"
UIPATH_CONFIG_FILE = "uipath.json"
UIPATH_BINDINGS_FILE = "bindings.json"
ENTRY_POINTS_FILE = "entry-points.json"
STUDIO_METADATA_FILE = "studio_metadata.json"
UIPROJ_FILE = "project.uiproj"


# Folder names
LEGACY_EVAL_FOLDER = "evals"
EVALS_FOLDER = "evaluations"
# Evaluators
CUSTOM_EVALUATOR_PREFIX = "file://"
