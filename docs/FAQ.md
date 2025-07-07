# Frequently Asked Questions (FAQ)

### Q: Why am I getting a "Failed to prepare environment" error when deploying my python agent to UiPath Cloud Platform?

#### Error Message

```json
{
    "Code": "Serverless.PythonCodedAgent.PrepareEnvironmentError",
    "Title": "Failed to prepare environment",
    "Detail": "An error occurred while installing the package dependencies. Please try again. If the error persists, please contact support.",
    "Category": "System",
    "Status": null
}
```

#### Visual Example

<picture data-light="../assets/env-preparation-failed-light.png" data-dark="../assets/env-preparation-failed-dark.png">
  <source
    media="(prefers-color-scheme: dark)"
    srcset="../assets/env-preparation-failed-dark.png"
  />
  <img
    src="../assets/env-preparation-failed-light.png"
  />
</picture>

*Example of the error as it appears in UiPath Cloud Platform*

#### Description

This error might occur when deploying coded-agents to UiPath Cloud Platform, even though the same project might work correctly in your local environment. The issue is often related to how Python packages are discovered and distributed during the cloud deployment process.

#### Common Causes

1. Multiple top-level packages or modules in your project structure
2. Improper configuration or formatting in the pyproject.toml or requirements.txt files

#### Solution

##### 1. Check Your Project Structure

- Ensure your Python files are organized under a non top-level directory (e.g., using the `src` layout)
- Follow the recommended project structure:

  ```plaintext
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

```toml
[tool.setuptools]
py-modules = []
packages = ["your_package"]
```

##### 3. Verify Dependencies

- Ensure all required dependencies are properly listed in your `requirements.txt` or `pyproject.toml`

#### Reference

For more detailed information about package discovery and configuration, refer to the [official setuptools documentation](https://setuptools.pypa.io/en/latest/userguide/package_discovery.html).

### Q: Why am I getting timeouts or "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed" errors?

The UiPath CLI automatically works with your corporate network setup, including proxy servers and security tools like ZScaler, by leveraging your system's native SSL certificate store.

#### Proxy Configuration

Configure these environment variables to route CLI traffic through your corporate proxy:

//// tab | Linux/macOS Bash

<!-- termynal -->
```bash
> export HTTP_PROXY=http://proxy.company.com:8080
> export HTTPS_PROXY=https://proxy.company.com:8080
> export NO_PROXY=localhost,127.0.0.1
> uipath auth
⠋ Authenticating with UiPath ...
✓  Authentication successful.
```

////

//// tab | Windows PowerShell

<!-- termynal -->
```powershell
> $env:HTTP_PROXY="http://proxy.company.com:8080"
> $env:HTTPS_PROXY="https://proxy.company.com:8080"
> $env:NO_PROXY="localhost,127.0.0.1"
> uipath auth
⠋ Authenticating with UiPath ...
✓  Authentication successful.
```

////

//// tab | Windows CMD

<!-- termynal -->
```cmd
> set HTTP_PROXY=http://proxy.company.com:8080
> set HTTPS_PROXY=https://proxy.company.com:8080
> set NO_PROXY=localhost,127.0.0.1
> uipath auth
⠋ Authenticating with UiPath ...
✓  Authentication successful.
```

////

#### Proxy Authentication

//// tab | Linux/macOS Bash

<!-- termynal -->
```bash
> export HTTP_PROXY=http://username:password@proxy.company.com:8080
> export HTTPS_PROXY=https://username:password@proxy.company.com:8080
> export NO_PROXY=localhost,127.0.0.1
> uipath publish
⠋ Fetching available package feeds...
✓  Package published successfully!
```

////

//// tab | Windows PowerShell

<!-- termynal -->
```powershell
> $env:HTTP_PROXY="http://username:password@proxy.company.com:8080"
> $env:HTTPS_PROXY="https://username:password@proxy.company.com:8080"
> $env:NO_PROXY="localhost,127.0.0.1"
> uipath publish
⠋ Fetching available package feeds...
✓  Package published successfully!
```

////

//// tab | Windows CMD

<!-- termynal -->
```cmd
> set HTTP_PROXY=http://username:password@proxy.company.com:8080
> set HTTPS_PROXY=https://username:password@proxy.company.com:8080
> set NO_PROXY=localhost,127.0.0.1
> uipath publish
⠋ Fetching available package feeds...
✓  Package published successfully!
```

////

/// tip
**For IT Administrators**: Add these environment variables to your Group Policy or system configuration:

```bash
HTTP_PROXY=http://your-proxy.company.com:8080
HTTPS_PROXY=https://your-proxy.company.com:8080
NO_PROXY=localhost,127.0.0.1,*.company.com
```
///

/// warning
The CLI uses a local HTTP server for the authentication callback. You must **exclude localhost** from your proxy using `NO_PROXY=localhost,127.0.0.1` or authentication will fail.
///

##### Troubleshooting
<!-- termynal -->
```bash
> # Test proxy connectivity
> curl -v --proxy $HTTP_PROXY https://cloud.uipath.com
*   Trying 192.168.1.100:8080...
* Connected to proxy.company.com (192.168.1.100) port 8080
✓ Connection successful

> # Test localhost exclusion
> curl --proxy $HTTP_PROXY http://localhost:8080
* Bypassing proxy for localhost
✓ Direct connection to localhost successful
```

#### SSL Certificates

The UiPath CLI automatically uses your system's certificate store (Windows Certificate Store, macOS Keychain, Linux ca-certificates). Corporate certificates installed via Group Policy or IT tools will be automatically recognized.

##### Troubleshooting SSL Issues

If you encounter SSL certificate errors:

1. **Disable SSL verification** (for testing only):

   //// tab | Linux/macOS Bash

   <!-- termynal -->
   ```bash
   > export UIPATH_DISABLE_SSL_VERIFY=true
   > uipath auth
   ⠋ Authenticating with UiPath ...
   ✓  Authentication successful.
   ```

   ////

   //// tab | Windows PowerShell

   <!-- termynal -->
   ```powershell
   > $env:UIPATH_DISABLE_SSL_VERIFY="true"
   > uipath auth
   ⠋ Authenticating with UiPath ...
   ✓  Authentication successful.
   ```

   ////

   //// tab | Windows CMD

   <!-- termynal -->
   ```cmd
   > set UIPATH_DISABLE_SSL_VERIFY=true
   > uipath auth
   ⠋ Authenticating with UiPath ...
   ✓  Authentication successful.
   ```

   ////

2. **Use custom certificate bundle** (if needed):

   //// tab | Linux/macOS Bash

   <!-- termynal -->
   ```bash
   > export SSL_CERT_FILE=/path/to/company-ca-bundle.pem
   > export REQUESTS_CA_BUNDLE=/path/to/company-ca-bundle.pem
   > uipath publish
   ⠋ Publishing most recent package...
   ✓  Package published successfully!
   ```

   ////

   //// tab | Windows PowerShell

   <!-- termynal -->
   ```powershell
   > $env:SSL_CERT_FILE="C:\certs\company-ca-bundle.pem"
   > $env:REQUESTS_CA_BUNDLE="C:\certs\company-ca-bundle.pem"
   > uipath publish
   ⠋ Publishing most recent package...
   ✓  Package published successfully!
   ```

   ////

   //// tab | Windows CMD

   <!-- termynal -->
   ```cmd
   > set SSL_CERT_FILE=C:\certs\company-ca-bundle.pem
   > set REQUESTS_CA_BUNDLE=C:\certs\company-ca-bundle.pem
   > uipath publish
   ⠋ Publishing most recent package...
   ✓  Package published successfully!
   ```

   ////


---

*Note: This FAQ will be updated as new information becomes available. If you continue experiencing issues after following these solutions, please contact UiPath support.*

