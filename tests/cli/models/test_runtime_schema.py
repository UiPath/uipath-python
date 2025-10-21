from pydantic import TypeAdapter

from uipath._cli.models.runtime_schema import RuntimeSchema


def test_runtime_schema_validation():
    # Arrange
    schema = {
        "runtime": {
            "internalArguments": {
                "resourceOverwrites": {
                    "resource.key": {
                        "name": "",
                        "folderPath": "",
                    }
                }
            }
        },
        "entryPoints": [
            {
                "filePath": "main.py",
                "uniqueId": "cb9d5d2b-1f16-420f-baeb-cf3d80269248",
                "type": "agent",
                "input": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number"},
                        "b": {"type": "number"},
                        "operator": {
                            "type": "string",
                            "enum": ["+", "-", "*", "/", "random"],
                        },
                    },
                    "required": ["a", "b", "operator"],
                },
                "output": {
                    "type": "object",
                    "properties": {"result": {"type": "number"}},
                    "required": ["result"],
                },
            }
        ],
        "bindings": {
            "version": "2.0",
            "resources": [
                {
                    "resource": "process",
                    "key": "process-key",
                    "value": {
                        "name": {
                            "defaultValue": "process-name",
                            "isExpression": False,
                            "displayName": "Process name",
                        }
                    },
                    "metadata": {
                        "subType": "agent",
                        "bindingsVersion": "2.2",
                        "solutionsSupport": "true",
                    },
                },
                {
                    "resource": "connection",
                    "key": "connection-key",
                    "value": {
                        "connectionId": {
                            "defaultValue": "connection-id",
                            "isExpression": False,
                            "displayName": "Connection ID",
                        }
                    },
                    "metadata": {
                        "connector": "uipath-salesforce-slack",
                        "useConnectionService": "true",
                        "bindingsVersion": "2.2",
                        "solutionsSupport": "true",
                    },
                },
                {
                    "resource": "app",
                    "key": "ActionApp",
                    "value": {
                        "name": {
                            "defaultValue": "ActionApp",
                            "isExpression": False,
                            "displayName": "App name",
                        }
                    },
                    "metadata": {"bindingsVersion": "2.2", "solutionsSupport": "true"},
                },
            ],
        },
    }

    # Act and Assert
    TypeAdapter(RuntimeSchema).validate_python(schema)
