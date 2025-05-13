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

---

*Note: This FAQ will be updated as new information becomes available. If you continue experiencing issues after following these solutions, please contact UiPath support.*
