# Frequently Asked Questions (FAQ)

### Q: Why am I getting a "Failed to prepare environment" error when deploying my python agent to UiPath Cloud Platform?

#### Error Message

```
{
    "Code": "Serverless.PythonCodedAgent.PrepareEnvironmentError",
    "Title": "Failed to prepare environment",
    "Detail": "An error occurred while installing the package dependencies. Please try again. If the error persists, please contact support.",
    "Category": "System",
    "Status": null
}
```

#### Visual Example

*Example of the error as it appears in UiPath Cloud Platform*

#### Description

This error might occur when deploying coded-agents to UiPath Cloud Platform, even though the same project might work correctly in your local environment. The issue is often related to how Python packages are discovered and distributed during the cloud deployment process.

#### Common Causes

1. Multiple top-level packages or modules in your project structure
1. Improper configuration or formatting in the pyproject.toml file

#### Solution

##### 1. Check Your Project Structure

- Ensure your Python files are organized under a non top-level directory (e.g., using the `src` layout)
- Follow the recommended project structure:

```
project_root/
├── src/
│   └── your_package/
│       ├── __init__.py
│       └── your_modules.py
├── pyproject.toml
└── setup.cfg/setup.py
```

##### 2. Configure Package Discovery

If you need to maintain your current project structure, you can configure custom package discovery in your `pyproject.toml`:

```
[tool.setuptools]
py-modules = []
packages = ["your_package"]
```

##### 3. Verify Dependencies

- Ensure all required dependencies are properly listed in your `pyproject.toml`

#### Reference

For more detailed information about package discovery and configuration, refer to the [official setuptools documentation](https://setuptools.pypa.io/en/latest/userguide/package_discovery.html).

### Q: Why am I getting timeouts or "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed" errors?

The UiPath CLI automatically works with your corporate network setup, including proxy servers and security tools like ZScaler, by leveraging your system's native SSL certificate store.

#### Proxy Configuration

Configure these environment variables to route CLI traffic through your corporate proxy:

export HTTP_PROXY=http://proxy.company.com:8080export HTTPS_PROXY=https://proxy.company.com:8080export NO_PROXY=localhost,127.0.0.1uipath auth⠋ Authenticating with UiPath ...\
✓ Authentication successful.

$env:HTTP_PROXY="http://proxy.company.com:8080"$env:HTTPS_PROXY="https://proxy.company.com:8080"$env:NO_PROXY="localhost,127.0.0.1"uipath auth⠋ Authenticating with UiPath ...\
✓ Authentication successful.

set HTTP_PROXY=http://proxy.company.com:8080set HTTPS_PROXY=https://proxy.company.com:8080set NO_PROXY=localhost,127.0.0.1uipath auth⠋ Authenticating with UiPath ...\
✓ Authentication successful.

#### Proxy Authentication

export HTTP_PROXY=http://username:password@proxy.company.com:8080export HTTPS_PROXY=https://username:password@proxy.company.com:8080export NO_PROXY=localhost,127.0.0.1uipath publish⠋ Fetching available package feeds...\
✓ Package published successfully!

$env:HTTP_PROXY="http://username:password@proxy.company.com:8080"$env:HTTPS_PROXY="https://username:password@proxy.company.com:8080"$env:NO_PROXY="localhost,127.0.0.1"uipath publish⠋ Fetching available package feeds...\
✓ Package published successfully!

set HTTP_PROXY=http://username:password@proxy.company.com:8080set HTTPS_PROXY=https://username:password@proxy.company.com:8080set NO_PROXY=localhost,127.0.0.1uipath publish⠋ Fetching available package feeds...\
✓ Package published successfully!

Tip

**For IT Administrators**: Add these environment variables to your Group Policy or system configuration:

```
HTTP_PROXY=http://your-proxy.company.com:8080
HTTPS_PROXY=https://your-proxy.company.com:8080
NO_PROXY=localhost,127.0.0.1,*.company.com
```

Warning

The CLI uses a local HTTP server for the authentication callback. You must **exclude localhost** from your proxy using `NO_PROXY=localhost,127.0.0.1` or authentication will fail.

##### Troubleshooting

# Test proxy connectivitycurl -v --proxy $HTTP_PROXY https://cloud.uipath.com\* Trying 192.168.1.100:8080...

\* Connected to proxy.company.com (192.168.1.100) port 8080\
✓ Connection successful

# Test localhost exclusioncurl --proxy $HTTP_PROXY http://localhost:8080\* Bypassing proxy for localhost

✓ Direct connection to localhost successful

#### SSL Certificates

The UiPath CLI automatically uses your system's certificate store (Windows Certificate Store, macOS Keychain, Linux ca-certificates). Corporate certificates installed via Group Policy or IT tools will be automatically recognized.

##### Troubleshooting SSL Issues

If you encounter SSL certificate errors:

1. **Disable SSL verification** (for testing only):

export UIPATH_DISABLE_SSL_VERIFY=trueuipath auth⠋ Authenticating with UiPath ...\
✓ Authentication successful.

$env:UIPATH_DISABLE_SSL_VERIFY="true"uipath auth⠋ Authenticating with UiPath ...\
✓ Authentication successful.

set UIPATH_DISABLE_SSL_VERIFY=trueuipath auth⠋ Authenticating with UiPath ...\
✓ Authentication successful.

2. **Use custom certificate bundle** (if needed):

export SSL_CERT_FILE=/path/to/company-ca-bundle.pemexport REQUESTS_CA_BUNDLE=/path/to/company-ca-bundle.pemuipath publish⠋ Publishing most recent package...\
✓ Package published successfully!

$env:SSL_CERT_FILE="C:\\certs\\company-ca-bundle.pem"$env:REQUESTS_CA_BUNDLE="C:\\certs\\company-ca-bundle.pem"uipath publish⠋ Publishing most recent package...\
✓ Package published successfully!

set SSL_CERT_FILE=C:\\certs\\company-ca-bundle.pemset REQUESTS_CA_BUNDLE=C:\\certs\\company-ca-bundle.pemuipath publish⠋ Publishing most recent package...\
✓ Package published successfully!

### Q: Why are my agent runs hanging on UiPath Cloud Platform?

#### Error Message

You may see errors like these in the logs panel:

```
[Error] .venv/lib/python3.14/site-packages/azure/monitor/opentelemetry/exporter/export/_base.py:472: SyntaxWarning: 'return' in a 'finally' block
[Error]   return ExportResult.FAILED_NOT_RETRYABLE  # pylint: disable=W0134
[Error] .venv/lib/python3.14/site-packages/azure/monitor/opentelemetry/exporter/export/_base.py:474: SyntaxWarning: 'return' in a 'finally' block
[Error]   return result  # pylint: disable=W0134
```

#### Description

If your Python agent runs are hanging or not completing when deployed to UiPath Cloud Platform's serverless environment, this may be caused by a library incompatibility issue from an outdated version of the UiPath Python library.

#### Solution

Ensure you're using **`uipath` version 2.1.169 or later**. This version includes fixes for serverless execution.

To check your current version:

uipath --versionuipath version 2.1.169

To upgrade to the latest version:

uv sync --upgrade-package uipathInstalled 1 package in 15ms

- uipath==2.1.140

* uipath==2.1.169

After upgrading, update your `pyproject.toml` to ensure the correct version is used in your deployment:

**pyproject.toml:**

```
[project]
dependencies = [
    "uipath>=2.1.169",
]
```

______________________________________________________________________

*Note: This FAQ will be updated as new information becomes available. If you continue experiencing issues after following these solutions, please contact UiPath support.*
