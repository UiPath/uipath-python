# Simple UiPath Coded Agents

This is a simple, standalone Coded Agent which does not require external dependencies.

After initialization, execute the agent using this sample command:
```
uipath run main.py '{"a": 0, "b": 1, "operator": "+"}'
```

# Run evaluations
```
uipath eval .\main.py .\evals\eval-sets\default.json --no-report --output-file output.json
```
