# Getting Started

## Using an Agent Based on LangGraph

To use the UiPath SDK with a LangGraph-based project:

1. Add the `uipath-langchain` package to your project:

    ```shell
    uv add uipath-langchain
    ```

2. Initialize the project by running the following command in your activated virtual environment:

    ```shell
    uipath init
    ```

    > **Note:**: The `uipath init` command will execute your code to analyze its structure and collect information about inputs and outputs.

3. Package and publish your project:
    ```shell
    uipath pack
    uipath publish
    ```

This will create and publish your package to the UiPath platform, making it available for use in your automation workflows.

For more examples and implementation patterns, check out the [sample projects](https://github.com/UiPath/uipath-langchain-python/tree/main/samples) in our GitHub repository.
