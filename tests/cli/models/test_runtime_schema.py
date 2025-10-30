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
    }

    # Act and Assert
    TypeAdapter(RuntimeSchema).validate_python(schema)
