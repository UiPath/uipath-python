import json

from uipath._cli.models.runtime_schema import EntryPoint, EntryPoints


class TestEntryPointModel:
    def test_entrypoint_from_dict(self) -> None:
        data = {
            "filePath": "agent",
            "uniqueId": "f620a11e-90fa-4506-8859-d8f147fdc31d",
            "type": "agent",
            "input": {"type": "object", "properties": {}},
            "output": {"type": "string"},
        }
        ep = EntryPoint.model_validate(data)
        assert ep.file_path == "agent"
        assert ep.type == "agent"
        assert ep.graph is None
        assert ep.metadata is None

    def test_entrypoint_with_graph(self) -> None:
        data = {
            "filePath": "agent",
            "uniqueId": "f620a11e-90fa-4506-8859-d8f147fdc31d",
            "type": "agent",
            "input": {"type": "object", "properties": {}},
            "output": {"type": "string"},
            "graph": {
                "nodes": [{"id": "n1", "name": "main", "type": "function"}],
                "edges": [],
            },
        }
        ep = EntryPoint.model_validate(data)
        assert ep.graph is not None
        assert len(ep.graph["nodes"]) == 1

    def test_entrypoint_roundtrip(self) -> None:
        data = {
            "filePath": "func",
            "uniqueId": "00000000-0000-0000-0000-000000000000",
            "type": "function",
            "input": {"type": "object", "properties": {"x": {"type": "string"}}},
            "output": {"type": "string"},
        }
        ep = EntryPoint.model_validate(data)
        dumped = ep.model_dump(by_alias=True, exclude_none=True)
        assert dumped["filePath"] == "func"
        assert dumped["type"] == "function"
        assert "graph" not in dumped


class TestEntryPointsModel:
    def test_entrypoints_from_file_content(self) -> None:
        content = {
            "$schema": "https://cloud.uipath.com/draft/2024-12/entry-point",
            "$id": "entry-points.json",
            "entryPoints": [
                {
                    "filePath": "agent",
                    "uniqueId": "f620a11e-90fa-4506-8859-d8f147fdc31d",
                    "type": "agent",
                    "input": {"type": "object", "properties": {}},
                    "output": {"type": "string"},
                },
                {
                    "filePath": "function",
                    "uniqueId": "0c34d779-78b1-4902-8657-a0ebf65d66af",
                    "type": "function",
                    "input": {"type": "object", "properties": {}},
                    "output": {"type": "string"},
                },
            ],
        }
        eps = EntryPoints.model_validate(content)
        assert len(eps.entrypoints) == 2
        assert eps.entrypoints[0].type == "agent"
        assert eps.entrypoints[1].type == "function"

    def test_entrypoints_roundtrip(self) -> None:
        content = {
            "$schema": "https://cloud.uipath.com/draft/2024-12/entry-point",
            "$id": "entry-points.json",
            "entryPoints": [
                {
                    "filePath": "main",
                    "uniqueId": "00000000-0000-0000-0000-000000000000",
                    "type": "function",
                    "input": {"type": "object", "properties": {}},
                    "output": {"type": "string"},
                },
            ],
        }
        eps = EntryPoints.model_validate(content)
        dumped = eps.model_dump(by_alias=True, exclude_none=True)
        assert dumped["$schema"] == content["$schema"]
        assert dumped["$id"] == content["$id"]
        assert len(dumped["entryPoints"]) == 1

    def test_entrypoints_json_serialization(self) -> None:
        content = {
            "$schema": "https://cloud.uipath.com/draft/2024-12/entry-point",
            "$id": "entry-points.json",
            "entryPoints": [
                {
                    "filePath": "test",
                    "uniqueId": "00000000-0000-0000-0000-000000000000",
                    "type": "agent",
                    "input": {"type": "object", "properties": {}},
                    "output": {"type": "string"},
                },
            ],
        }
        eps = EntryPoints.model_validate(content)
        json_str = eps.model_dump_json(by_alias=True, exclude_none=True)
        parsed = json.loads(json_str)
        assert parsed["entryPoints"][0]["type"] == "agent"
