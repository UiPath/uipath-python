import json

import inflection


def _convert_to_snake_case(old_dict):
    new_dict = {}
    for key, value in old_dict.items():
        new_key = inflection.underscore(key)
        new_dict[new_key] = value
    return new_dict


def _convert_to_camel_case(old_dict):
    new_dict = {}
    for key, value in old_dict.items():
        if isinstance(value, list):
            new_value = [
                _convert_to_camel_case(v.__dict__) if hasattr(v, "__dict__") else v
                for v in value
            ]
        elif hasattr(value, "__dict__"):
            new_value = _convert_to_camel_case(value.__dict__)
        else:
            new_value = value
        new_key = inflection.camelize(key, False)
        new_dict[new_key] = new_value
    return new_dict


class InputOutput:
    def __init__(self, type=None, properties=None, required=None):
        self.type = type
        self.properties = properties if properties else {}
        self.required = required if required else []


class EntryPoint:
    def __init__(
        self, file_path=None, unique_id=None, type=None, input=None, output=None
    ):
        self.file_path = file_path
        self.unique_id = unique_id
        self.type = type
        self.input = (
            InputOutput(**_convert_to_snake_case(input))
            if isinstance(input, dict)
            else input
        )
        self.output = (
            InputOutput(**_convert_to_snake_case(output))
            if isinstance(output, dict)
            else output
        )

    def __str__(self):
        data = self.__dict__
        camel_cased_data = _convert_to_camel_case(data)
        return json.dumps(camel_cased_data, separators=(",", ":"))


class Bindings:
    def __init__(self, version=None, resources=None):
        self.version = version
        self.resources = resources if resources else []


class Settings:
    def __init__(
        self,
        file_extensions_included=None,
        files_included=None,
        files_excluded=None,
        directories_excluded=None,
    ):
        self.file_extensions_included = (
            file_extensions_included if file_extensions_included else []
        )
        self.files_included = files_included if files_included else []
        self.files_excluded = files_excluded if files_excluded else []
        self.directories_excluded = directories_excluded if directories_excluded else []


class UiPathJson:
    def __init__(self, entry_points=None, bindings=None, settings=None):
        self.entry_points = (
            [EntryPoint(**ep) if isinstance(ep, dict) else ep for ep in entry_points]
            if entry_points
            else []
        )
        self.bindings = (
            Bindings(**bindings)
            if isinstance(bindings, dict)
            else bindings
            if bindings
            else []
        )
        self.settings = (
            Settings(**settings)
            if isinstance(settings, dict)
            else settings
            if settings
            else []
        )

    @classmethod
    def from_json(cls, json_str):
        data = json.loads(json_str)
        entry_points = [
            _convert_to_snake_case(ep) for ep in data.get("entryPoints", [])
        ]
        bindings = _convert_to_snake_case(data.get("bindings", {}))
        settings = _convert_to_snake_case(data.get("settings", {}))
        return cls(entry_points, bindings, settings)

    def to_json(self):
        data = self.__dict__
        camel_cased_data = _convert_to_camel_case(data)
        return json.dumps(camel_cased_data, separators=(",", ":"))
