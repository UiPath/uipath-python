# Simple UiPath Coded Agents

This is a simple, standalone Coded Agent which does not require external dependencies.

After initialization, execute the agent using this sample command:
```
uipath run main.py '{"a": 0, "b": 1, "operator": "+"}'
```

# Run evaluations
```
uipath eval .\main.py .\evaluations\eval-sets\default.json --no-report --output-file output.json
```

# Add and register custom evaluator

1. (Optional) Add a new evaluator -> can be created manually in the evaluations/custom-evaluators directory
```
uipath add evaluator my_custom_evaluator
```
2. Implement the logic

3. Register the evaluator
```
uipath register evaluator my_custom_evaluator
```
4. Apply it to any dataset
